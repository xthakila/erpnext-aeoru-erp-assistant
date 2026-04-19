"""Backend endpoints for Claude Code CLI management.

Provides auth status checking, login flow, and safe command execution
from the browser-based terminal in AI Assistant Settings.
"""
import frappe
import json
import os
import re
import subprocess


# Commands allowed via the terminal (whitelist for safety)
ALLOWED_COMMANDS = {
    "auth-status",   # claude auth status
    "auth-login",    # claude auth login (special handling)
    "auth-logout",   # claude auth logout
    "version",       # claude --version
    "doctor",        # claude doctor
    "status",        # claude status
}

AUTH_OUTPUT_FILE = "/tmp/claude-auth-output.txt"
AUTH_CODE_FILE = "/tmp/claude-auth-code.txt"
AUTH_RESULT_FILE = "/tmp/claude-auth-result.txt"
AUTH_SCRIPT_FILE = "/tmp/claude-auth-worker.sh"


def _get_cli_path() -> str:
    """Get the Claude CLI binary path from settings."""
    try:
        settings = frappe.get_single("AI Assistant Settings")
        return settings.claude_code_cli_path or "/usr/local/bin/claude"
    except Exception:
        return "/usr/local/bin/claude"


def _run_cli(args: list, timeout: int = 30) -> dict:
    """Run a claude CLI command and return structured output."""
    cli_path = _get_cli_path()
    cmd = [cli_path] + args

    env = os.environ.copy()
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)
    env.pop("CLAUDE_CODE_SESSION_ID", None)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",
            env=env,
        )
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout.strip() if proc.stdout else "",
            "stderr": proc.stderr.strip() if proc.stderr else "",
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": f"Command timed out after {timeout}s", "returncode": -1}
    except FileNotFoundError:
        return {"success": False, "stdout": "", "stderr": f"CLI not found at: {cli_path}", "returncode": -1}
    except OSError as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}


@frappe.whitelist()
def check_auth():
    """Check Claude Code authentication status."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Only System Manager can access Claude Code settings.", frappe.PermissionError)

    result = _run_cli(["auth", "status"])

    output = result.get("stdout", "") + "\n" + result.get("stderr", "")
    authenticated = False
    account = ""

    if result["success"]:
        authenticated = True
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', output)
        if email_match:
            account = email_match.group(0)

    return {
        "authenticated": authenticated,
        "account": account,
        "output": output.strip(),
        "cli_path": _get_cli_path(),
    }


@frappe.whitelist()
def start_login():
    """Start Claude Code OAuth login flow.

    Creates a background shell script that:
    1. Starts `claude auth login` with expect-like stdin handling
    2. Captures the auth URL to a file
    3. Polls for a code file written by submit_auth_code()
    4. Feeds the code to the CLI's stdin
    5. Writes the result
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Only System Manager can access Claude Code settings.", frappe.PermissionError)

    import time

    # Clean up any previous login
    _cleanup_auth_files()
    subprocess.run(["pkill", "-f", "claude-auth-worker"], capture_output=True)
    time.sleep(0.5)

    cli_path = _get_cli_path()

    # Write a helper script that handles the interactive auth flow
    script = f"""#!/bin/bash
# claude-auth-worker: manages interactive auth login
export BROWSER=echo
unset CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SESSION_ID

# Remove stale files
rm -f {AUTH_CODE_FILE} {AUTH_RESULT_FILE}

# Run claude auth login, feeding stdin from a loop that waits for the code file
{{
    # Wait for the code file to appear (poll every 0.5s, up to 5 minutes)
    for i in $(seq 1 600); do
        if [ -f {AUTH_CODE_FILE} ]; then
            cat {AUTH_CODE_FILE}
            break
        fi
        sleep 0.5
    done
}} | {cli_path} auth login > {AUTH_OUTPUT_FILE} 2>&1

# Write result
{cli_path} auth status > {AUTH_RESULT_FILE} 2>&1
"""
    with open(AUTH_SCRIPT_FILE, "w") as f:
        f.write(script)
    os.chmod(AUTH_SCRIPT_FILE, 0o755)

    # Start the worker script in background
    subprocess.Popen(
        ["bash", AUTH_SCRIPT_FILE],
        cwd="/tmp",
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for the URL to appear in output
    auth_url = None
    output = ""
    for _ in range(50):  # up to 10 seconds
        time.sleep(0.2)
        try:
            with open(AUTH_OUTPUT_FILE, "r") as f:
                output = f.read()
            url_match = re.search(r'https?://[^\s<>"\']+', output)
            if url_match:
                auth_url = url_match.group(0)
                break
        except FileNotFoundError:
            pass

    return {
        "auth_url": auth_url,
        "output": output.strip(),
        "message": "Open the URL, authenticate, then paste the code below and press Enter." if auth_url else "Could not extract auth URL.",
        "needs_code": True,
    }


@frappe.whitelist()
def submit_auth_code(code: str):
    """Submit the OAuth code to the waiting auth worker.

    Writes the code to a file that the background worker script polls for.
    The worker reads it and feeds it to claude auth login's stdin.
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Only System Manager can access Claude Code settings.", frappe.PermissionError)

    if not code or not code.strip():
        return {"success": False, "message": "No code provided."}

    import time

    try:
        # Write the code — the worker script is polling for this file
        with open(AUTH_CODE_FILE, "w") as f:
            f.write(code.strip() + "\n")

        # Wait for the CLI to process the code and write the result
        for _ in range(20):  # up to 10 seconds
            time.sleep(0.5)
            if os.path.exists(AUTH_RESULT_FILE):
                break

        # Read output
        output = ""
        try:
            with open(AUTH_OUTPUT_FILE, "r") as f:
                output = f.read()
        except FileNotFoundError:
            pass

        # Check auth status
        result = _run_cli(["auth", "status"])
        status_output = result.get("stdout", "") + "\n" + result.get("stderr", "")
        authenticated = result.get("success", False)

        return {
            "success": authenticated,
            "output": output.strip(),
            "status": status_output.strip(),
            "message": "Authentication successful!" if authenticated else "Authentication may have failed. Check status.",
        }

    except OSError as e:
        return {"success": False, "message": f"Error submitting code: {e}"}


def _cleanup_auth_files():
    """Remove auth temp files."""
    for f in [AUTH_OUTPUT_FILE, AUTH_CODE_FILE, AUTH_RESULT_FILE, AUTH_SCRIPT_FILE]:
        try:
            os.unlink(f)
        except OSError:
            pass


@frappe.whitelist()
def run_command(command: str):
    """Run a whitelisted Claude CLI command from the terminal."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Only System Manager can access Claude Code terminal.", frappe.PermissionError)

    if not command or not command.strip():
        return {"success": False, "stdout": "", "stderr": "No command provided."}

    cmd_parts = command.strip().split()
    cmd_key = "-".join(cmd_parts[:2]) if len(cmd_parts) >= 2 else cmd_parts[0]

    if cmd_parts[0] == "--version" or cmd_parts[0] == "version":
        return _run_cli(["--version"])

    if cmd_key == "auth-status":
        return _run_cli(["auth", "status"])

    if cmd_key == "auth-logout":
        return _run_cli(["auth", "logout"])

    if cmd_key == "auth-login":
        login_result = start_login()
        return {
            "success": True,
            "stdout": login_result.get("output", ""),
            "stderr": login_result.get("message", ""),
            "auth_url": login_result.get("auth_url"),
        }

    if cmd_parts[0] == "doctor":
        return _run_cli(["doctor"], timeout=60)

    if cmd_parts[0] == "status":
        return _run_cli(["status"])

    allowed = ", ".join(sorted(ALLOWED_COMMANDS))
    return {
        "success": False,
        "stdout": "",
        "stderr": f"Command not allowed. Permitted commands: {allowed}",
    }


@frappe.whitelist()
def get_version():
    """Get Claude Code CLI version."""
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Only System Manager can access Claude Code settings.", frappe.PermissionError)

    result = _run_cli(["--version"])
    version = result.get("stdout", "").strip()
    return {"version": version, "installed": result["success"]}
