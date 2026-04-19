from frappe import _


def get_data():
    return [
        {
            "module_name": "Aeoru AI",
            "type": "module",
            "label": _("Aeoru AI"),
            "icon": "octicon octicon-hubot",
            "color": "#2490EF",
            "description": _("AI Assistant for ERPNext"),
        }
    ]
