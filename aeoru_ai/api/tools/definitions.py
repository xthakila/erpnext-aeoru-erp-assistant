"""Tool definitions for ERPNext AI Assistant.

Each tool is a dict with:
- name: Unique tool name
- description: What the tool does (guides AI behavior)
- parameters: JSON Schema for tool arguments
- destructive: Whether this is a destructive action requiring confirmation
"""

ALL_TOOLS = [
    {
        "name": "get_doctype_schema",
        "description": (
            "Get the schema (fields, types, required flags) for any ERPNext DocType. "
            "ALWAYS call this before create_document or update_document to understand "
            "what fields are available and required."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The DocType name, e.g., 'Customer', 'Sales Invoice', 'Employee'"
                }
            },
            "required": ["doctype"]
        },
        "destructive": False,
    },
    {
        "name": "create_document",
        "description": (
            "Create a new ERPNext document. ALWAYS call get_doctype_schema first to know "
            "the required fields. If any required field is missing from the user's request, "
            "ASK the user for it. NEVER fabricate or guess values for required fields."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The DocType to create, e.g., 'Customer'"
                },
                "values": {
                    "type": "object",
                    "description": "Field values for the new document"
                }
            },
            "required": ["doctype", "values"]
        },
        "destructive": False,
    },
    {
        "name": "get_document",
        "description": "Read a single document by its name/ID. Returns all fields.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The DocType, e.g., 'Customer'"
                },
                "name": {
                    "type": "string",
                    "description": "The document name/ID"
                }
            },
            "required": ["doctype", "name"]
        },
        "destructive": False,
    },
    {
        "name": "list_documents",
        "description": (
            "Search and list documents with filters, field selection, ordering, and pagination. "
            "Use this to find documents matching criteria."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The DocType to list"
                },
                "filters": {
                    "type": "object",
                    "description": "Filter criteria, e.g., {\"status\": \"Active\", \"territory\": \"India\"}"
                },
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Fields to return. Default: ['name', 'title/subject']"
                },
                "order_by": {
                    "type": "string",
                    "description": "Sort order, e.g., 'creation desc'"
                },
                "limit_page_length": {
                    "type": "integer",
                    "description": "Max results to return. Default: 20"
                },
                "limit_start": {
                    "type": "integer",
                    "description": "Offset for pagination. Default: 0"
                }
            },
            "required": ["doctype"]
        },
        "destructive": False,
    },
    {
        "name": "update_document",
        "description": "Update fields on an existing document.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The DocType"
                },
                "name": {
                    "type": "string",
                    "description": "The document name/ID to update"
                },
                "values": {
                    "type": "object",
                    "description": "Fields to update with new values"
                }
            },
            "required": ["doctype", "name", "values"]
        },
        "destructive": False,
    },
    {
        "name": "delete_document",
        "description": (
            "Delete a document permanently. This is a DESTRUCTIVE action. "
            "Always confirm with the user before deleting."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The DocType"
                },
                "name": {
                    "type": "string",
                    "description": "The document name/ID to delete"
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "Must be true to execute deletion. Set false initially."
                }
            },
            "required": ["doctype", "name"]
        },
        "destructive": True,
    },
    {
        "name": "submit_document",
        "description": (
            "Submit a document (docstatus 0 → 1). Only works on submittable DocTypes. "
            "This is a DESTRUCTIVE action — submitted documents can only be cancelled, not edited."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The DocType"
                },
                "name": {
                    "type": "string",
                    "description": "The document name/ID to submit"
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "Must be true to execute submission. Set false initially."
                }
            },
            "required": ["doctype", "name"]
        },
        "destructive": True,
    },
    {
        "name": "cancel_document",
        "description": (
            "Cancel a submitted document (docstatus 1 → 2). "
            "This is a DESTRUCTIVE action that cannot be undone."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The DocType"
                },
                "name": {
                    "type": "string",
                    "description": "The document name/ID to cancel"
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "Must be true to execute cancellation. Set false initially."
                }
            },
            "required": ["doctype", "name"]
        },
        "destructive": True,
    },
    {
        "name": "run_report",
        "description": "Execute a Frappe/ERPNext report and return results.",
        "parameters": {
            "type": "object",
            "properties": {
                "report_name": {
                    "type": "string",
                    "description": "The report name, e.g., 'General Ledger', 'Accounts Receivable'"
                },
                "filters": {
                    "type": "object",
                    "description": "Report filters"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return. Default: 50"
                }
            },
            "required": ["report_name"]
        },
        "destructive": False,
    },
    {
        "name": "get_count",
        "description": "Count documents matching filters.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctype": {
                    "type": "string",
                    "description": "The DocType to count"
                },
                "filters": {
                    "type": "object",
                    "description": "Filter criteria"
                }
            },
            "required": ["doctype"]
        },
        "destructive": False,
    },
]

# Lookup helpers
TOOL_MAP = {t["name"]: t for t in ALL_TOOLS}
DESTRUCTIVE_TOOLS = {t["name"] for t in ALL_TOOLS if t.get("destructive")}
