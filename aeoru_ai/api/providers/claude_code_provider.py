import frappe
import json
import os
import subprocess
from .base import BaseProvider, AIResponse, ToolResult


class ClaudeCodeProvider(BaseProvider):
    """Provider that invokes the Claude Code CLI binary via subprocess.

    Unlike API providers, this is single-shot: Claude Code handles tool use
    internally and returns a final answer. supports_tool_calls = False
    tells chat.py to skip the agentic loop.
    """

    REDIS_KEY = "aeoru_ai:claude_code:active_count"

    def __init__(self, model: str = "sonnet", cli_path: str = "/usr/local/bin/claude",
                 max_budget_usd: float = 1.00, timeout: int = 120,
                 max_concurrent: int = 3, allowed_tools: str = "",
                 mcp_server_path: str = ""):
        super().__init__(api_key=None, model=model)
        self.cli_path = cli_path
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.allowed_tools = allowed_tools
        self.mcp_server_path = mcp_server_path
        self.session_id = None  # Set by chat.py from conversation

    @property
    def supports_tool_calls(self) -> bool:
        return False

    def chat(self, messages: list, tools: list = None, system_prompt: str = "") -> AIResponse:
        """Run Claude Code CLI with the conversation and return the result."""
        prompt_text = self._build_prompt(messages)
        cmd = self._build_command(system_prompt)

        if not self._acquire_slot():
            return AIResponse(
                text="Claude Code is currently at maximum capacity "
                     f"({self.max_concurrent} concurrent requests). Please try again in a moment.",
                usage={"error": "concurrency_limit"}
            )

        try:
            return self._run_cli(cmd, prompt_text)
        finally:
            self._release_slot()

    def format_tool_result(self, tool_result: ToolResult) -> dict:
        """No-op: Claude Code handles tools internally."""
        return {"role": "user", "content": tool_result.content}

    def format_tool_calls_message(self, response: AIResponse) -> dict:
        """No-op: Claude Code handles tools internally."""
        return {"role": "assistant", "content": response.text}

    def _build_prompt(self, messages: list) -> str:
        """Build prompt text from message history.

        When resuming a session (self.session_id is set), only send the
        latest user message since Claude Code already has the prior context.
        When starting fresh, flatten the full history.
        """
        if self.session_id:
            # Resume mode: only the latest user message
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    return msg.get("content", "")
            return ""

        # Fresh session: flatten full history
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
        return "\n\n".join(parts)

    def _build_command(self, system_prompt: str) -> list:
        """Build the claude CLI command with flags."""
        cmd = [
            self.cli_path,
            "-p",  # print mode (non-interactive)
            "--output-format", "json",
            "--model", self.model,
            "--max-turns", "25",
            "--permission-mode", "dontAsk",
        ]

        if self.max_budget_usd > 0:
            cmd.extend(["--max-budget-usd", str(self.max_budget_usd)])

        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        if self.session_id:
            cmd.extend(["--resume", self.session_id])

        if self.allowed_tools:
            for tool in self.allowed_tools.strip().split("\n"):
                tool = tool.strip()
                if tool:
                    cmd.extend(["--allowedTools", tool])

        # Connect the Frappe MCP server for ERPNext document operations
        if self.mcp_server_path:
            mcp_config = json.dumps({
                "mcpServers": {
                    "frappe": {
                        "command": self.mcp_server_path,
                        "args": []
                    }
                }
            })
            cmd.extend(["--mcp-config", mcp_config])
            # Pre-allow all Frappe MCP tools
            frappe_tools = [
                "mcp__frappe__get_doctype_schema",
                "mcp__frappe__create_document",
                "mcp__frappe__get_document",
                "mcp__frappe__list_documents",
                "mcp__frappe__update_document",
                "mcp__frappe__delete_document",
                "mcp__frappe__submit_document",
                "mcp__frappe__cancel_document",
                "mcp__frappe__run_report",
                "mcp__frappe__get_count",
            ]
            for tool in frappe_tools:
                cmd.extend(["--allowedTools", tool])

        return cmd

    def _run_cli(self, cmd: list, prompt_text: str) -> AIResponse:
        """Execute the CLI subprocess and parse the JSON output."""
        # Inherit env but remove markers that cause nested-session errors
        env = os.environ.copy()
        env.pop("CLAUDE_CODE_ENTRYPOINT", None)
        env.pop("CLAUDE_CODE_SESSION_ID", None)

        try:
            proc = subprocess.run(
                cmd,
                input=prompt_text,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd="/tmp",
                env=env,
            )
        except subprocess.TimeoutExpired:
            return AIResponse(
                text=f"Claude Code request timed out after {self.timeout} seconds.",
                usage={"error": "timeout"}
            )
        except FileNotFoundError:
            return AIResponse(
                text=f"Claude Code CLI not found at: {self.cli_path}",
                usage={"error": "cli_not_found"}
            )
        except OSError as e:
            return AIResponse(
                text=f"Failed to execute Claude Code CLI: {e}",
                usage={"error": "os_error"}
            )

        if proc.returncode != 0:
            stderr = proc.stderr.strip() if proc.stderr else "Unknown error"
            # Still try to parse stdout in case there's partial output
            if proc.stdout and proc.stdout.strip():
                return self._parse_output(proc.stdout)
            return AIResponse(
                text=f"Claude Code error: {stderr}",
                usage={"error": "cli_error", "stderr": stderr}
            )

        return self._parse_output(proc.stdout)

    def _parse_output(self, stdout: str) -> AIResponse:
        """Parse the JSON output from Claude Code CLI.

        Claude Code --output-format json returns a JSON object with:
        - result: the final text response
        - session_id: CLI session ID for --resume
        - input_tokens, output_tokens, total_cost_usd, num_turns: usage stats
        """
        if not stdout or not stdout.strip():
            return AIResponse(text="No response from Claude Code.", usage={"error": "empty_response"})

        try:
            data = json.loads(stdout.strip())
        except json.JSONDecodeError:
            # If not valid JSON, treat raw text as the response
            return AIResponse(text=stdout.strip(), usage={})

        result_text = ""
        cli_session_id = None
        usage = {}

        if isinstance(data, dict):
            result_text = data.get("result", data.get("text", ""))
            cli_session_id = data.get("session_id")
            usage = {
                "input_tokens": data.get("input_tokens", 0),
                "output_tokens": data.get("output_tokens", 0),
                "total_cost_usd": data.get("total_cost_usd", 0),
                "num_turns": data.get("num_turns", 0),
            }
            if cli_session_id:
                usage["cli_session_id"] = cli_session_id
        elif isinstance(data, list):
            # Some output formats return a list of message objects
            text_parts = []
            for item in data:
                if isinstance(item, dict):
                    if item.get("type") == "result":
                        result_text = item.get("result", "")
                        cli_session_id = item.get("session_id")
                    elif item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
            if not result_text and text_parts:
                result_text = "\n".join(text_parts)
            if cli_session_id:
                usage["cli_session_id"] = cli_session_id
        else:
            result_text = str(data)

        return AIResponse(text=result_text, usage=usage)

    def _acquire_slot(self) -> bool:
        """Try to acquire a concurrency slot using Redis INCR with check."""
        try:
            redis = frappe.cache()
            current = int(redis.get(self.REDIS_KEY) or 0)
            if current >= self.max_concurrent:
                return False
            redis.incrby(self.REDIS_KEY, 1)
            redis.expire(self.REDIS_KEY, 300)  # 5-min safety TTL
            return True
        except Exception as e:
            frappe.log_error(f"Redis concurrency acquire error: {e}", "Claude Code Provider")
            return True  # Fail open if Redis is down

    def _release_slot(self):
        """Release a concurrency slot."""
        try:
            redis = frappe.cache()
            current = int(redis.get(self.REDIS_KEY) or 0)
            if current > 0:
                redis.decrby(self.REDIS_KEY, 1)
        except Exception as e:
            frappe.log_error(f"Redis concurrency release error: {e}", "Claude Code Provider")
