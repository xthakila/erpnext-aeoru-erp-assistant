app_name = "aeoru_ai"
app_title = "Aeoru AI"
app_publisher = "Aeoru"
app_description = "AI Assistant for ERPNext"
app_email = "dev@aeoru.io"
app_license = "MIT"

required_apps = ["frappe", "erpnext"]

app_include_js = [
    "/assets/aeoru_ai/js/ai_assistant.js",
    "/assets/aeoru_ai/js/ai_assistant_panel.js",
    "/assets/aeoru_ai/js/ai_assistant_message.js",
    "/assets/aeoru_ai/js/claude_terminal.js",
]

app_include_css = [
    "/assets/aeoru_ai/css/ai_assistant.css",
    "/assets/aeoru_ai/css/claude_terminal.css",
]

# Installation
after_install = "aeoru_ai.setup.after_install"
