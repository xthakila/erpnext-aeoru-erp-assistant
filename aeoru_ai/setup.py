import frappe
import shutil


def after_install():
    """Create default AI Assistant Settings after install.

    Auto-enables Claude Code if the CLI binary is found,
    otherwise falls back to Claude API (disabled until key is set).
    """
    settings = frappe.get_single("AI Assistant Settings")

    # Detect Claude Code CLI
    cli_path = shutil.which("claude") or "/usr/local/bin/claude"
    has_claude_code = shutil.which("claude") is not None

    # Set defaults
    settings.default_provider = "Claude Code" if has_claude_code else "Claude"
    settings.enabled = 1 if has_claude_code else 0
    settings.claude_model = "claude-sonnet-4-20250514"
    settings.claude_code_cli_path = cli_path
    settings.claude_code_model = "sonnet"
    settings.claude_code_max_budget = 1.0
    settings.claude_code_timeout = 120
    settings.claude_code_max_concurrent = 3
    settings.temperature = 0.3
    settings.max_tokens = 4096
    settings.require_confirmation = 1
    settings.save(ignore_permissions=True)
    frappe.db.commit()

    if has_claude_code:
        frappe.logger().info("AI Assistant: Claude Code CLI found, enabled as default provider")
    else:
        frappe.logger().info("AI Assistant: Claude Code CLI not found, disabled until API key is configured")
