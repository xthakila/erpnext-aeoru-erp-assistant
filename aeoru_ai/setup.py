import frappe
import json
import shutil


def after_install():
    """Create default AI Assistant Settings after install.

    Auto-enables Claude Code if the CLI binary is found,
    otherwise falls back to Claude API (disabled until key is set).
    Also injects Aeoru AI into the Desktop home page.
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

    # Add Aeoru AI to the Desktop home page
    _add_to_desktop()


def _add_to_desktop():
    """Inject Aeoru AI shortcut into the Home workspace Desktop grid."""
    try:
        home = frappe.get_doc("Workspace", "Home")
        content = json.loads(home.content or "[]")

        # Check if already added
        for item in content:
            if item.get("data", {}).get("shortcut_name") == "AI Assistant":
                return  # Already exists

        # Add shortcut entry to the content grid
        content.append({
            "id": "aeoru_ai_shortcut",
            "type": "shortcut",
            "data": {
                "shortcut_name": "AI Assistant",
                "col": 3,
            },
        })

        # Add the shortcut definition
        existing_shortcuts = [s.label for s in (home.shortcuts or [])]
        if "AI Assistant" not in existing_shortcuts:
            home.append("shortcuts", {
                "label": "AI Assistant",
                "link_to": "AI Assistant Settings",
                "type": "DocType",
                "color": "Purple",
            })

        home.content = json.dumps(content)
        home.save(ignore_permissions=True)
        frappe.db.commit()
        frappe.logger().info("AI Assistant: Added to Desktop home page")
    except Exception as e:
        frappe.logger().warning(f"AI Assistant: Could not add to Desktop: {e}")
