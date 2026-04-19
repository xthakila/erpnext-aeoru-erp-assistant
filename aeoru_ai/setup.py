import frappe


def after_install():
    """Create default AI Assistant Settings after install."""
    if not frappe.db.exists("AI Assistant Settings"):
        settings = frappe.new_doc("AI Assistant Settings")
        settings.enabled = 0
        settings.default_provider = "Claude"
        settings.claude_model = "claude-sonnet-4-20250514"
        settings.temperature = 0.3
        settings.max_tokens = 4096
        settings.require_confirmation = 1
        settings.insert(ignore_permissions=True)
        frappe.db.commit()
