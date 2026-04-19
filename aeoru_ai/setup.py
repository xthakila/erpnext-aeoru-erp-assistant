import frappe
import shutil


def after_install():
    """Create default AI Assistant Settings after install.

    Auto-enables Claude Code if the CLI binary is found,
    otherwise falls back to Claude API (disabled until key is set).
    Also adds Aeoru AI to the Desktop icon grid.
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

    # Add Aeoru AI icon to the Desktop grid
    _add_desktop_icon()


def _add_desktop_icon():
    """Create a Desktop Icon so Aeoru AI appears on the v16 Desktop grid."""
    try:
        # Create Workspace Sidebar record (required by Desktop Icon link validation)
        if not frappe.db.exists("Workspace Sidebar", "Aeoru AI"):
            frappe.get_doc({
                "doctype": "Workspace Sidebar",
                "name": "Aeoru AI",
                "title": "Aeoru AI",
            }).insert(ignore_permissions=True, ignore_if_duplicate=True)

        # Create the Desktop Icon
        if not frappe.db.exists("Desktop Icon", {"label": "Aeoru AI"}):
            frappe.get_doc({
                "doctype": "Desktop Icon",
                "label": "Aeoru AI",
                "link_type": "Workspace Sidebar",
                "link_to": "Aeoru AI",
                "app": "aeoru_ai",
                "icon": "chat",
                "icon_type": "Link",
                "standard": 1,
                "hidden": 0,
                "idx": 45,
            }).insert(ignore_permissions=True)

        frappe.db.commit()
        frappe.clear_cache()
        frappe.logger().info("AI Assistant: Desktop icon created")
    except Exception as e:
        frappe.logger().warning(f"AI Assistant: Could not create Desktop icon: {e}")
