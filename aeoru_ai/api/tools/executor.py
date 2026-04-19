import frappe
import json
from aeoru_ai.api.tools.definitions import DESTRUCTIVE_TOOLS
from aeoru_ai.api.tools.schema_helpers import get_doctype_info, get_required_fields
from aeoru_ai.api.providers.base import ToolCall, ToolResult


def execute_tool(tool_call: ToolCall, confirmed: bool = False) -> ToolResult:
    """Execute a tool call and return the result.

    All operations run as the logged-in user (permission enforcement).
    Destructive operations require confirmed=True.
    """
    try:
        name = tool_call.name
        args = tool_call.arguments

        # Gate destructive actions
        if name in DESTRUCTIVE_TOOLS and not confirmed and not args.get("confirmed"):
            return ToolResult(
                tool_call_id=tool_call.id,
                content=json.dumps({
                    "status": "confirmation_required",
                    "action": name,
                    "details": args,
                    "message": f"This is a destructive action ({name}). Please confirm to proceed.",
                }),
                is_error=False,
            )

        # Dispatch to handler
        handlers = {
            "get_doctype_schema": _handle_get_schema,
            "create_document": _handle_create,
            "get_document": _handle_get,
            "list_documents": _handle_list,
            "update_document": _handle_update,
            "delete_document": _handle_delete,
            "submit_document": _handle_submit,
            "cancel_document": _handle_cancel,
            "run_report": _handle_report,
            "get_count": _handle_count,
        }

        handler = handlers.get(name)
        if not handler:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Unknown tool: {name}",
                is_error=True,
            )

        result = handler(args)
        return ToolResult(
            tool_call_id=tool_call.id,
            content=json.dumps(result, default=str),
            is_error=False,
        )

    except frappe.PermissionError as e:
        return ToolResult(
            tool_call_id=tool_call.id,
            content=f"Permission denied: {str(e)}. The current user does not have access to perform this operation.",
            is_error=True,
        )
    except frappe.DoesNotExistError as e:
        return ToolResult(
            tool_call_id=tool_call.id,
            content=f"Not found: {str(e)}",
            is_error=True,
        )
    except Exception as e:
        frappe.log_error(f"Tool execution error ({tool_call.name}): {str(e)}", "AI Assistant")
        return ToolResult(
            tool_call_id=tool_call.id,
            content=f"Error executing {tool_call.name}: {str(e)}",
            is_error=True,
        )


def _handle_get_schema(args: dict) -> dict:
    """Get DocType schema information."""
    doctype = args["doctype"]
    if not frappe.db.exists("DocType", doctype):
        raise frappe.DoesNotExistError(f"DocType '{doctype}' does not exist")
    return get_doctype_info(doctype)


def _handle_create(args: dict) -> dict:
    """Create a new document."""
    doctype = args["doctype"]
    values = args.get("values", {})

    # Validate required fields
    required = get_required_fields(doctype)
    missing = [f["fieldname"] for f in required if f["fieldname"] not in values and not f.get("default")]
    if missing:
        return {
            "status": "missing_required_fields",
            "missing_fields": missing,
            "message": f"Cannot create {doctype}. Missing required fields: {', '.join(missing)}",
        }

    doc = frappe.get_doc({"doctype": doctype, **values})
    doc.insert()
    frappe.db.commit()

    return {
        "status": "created",
        "doctype": doctype,
        "name": doc.name,
        "message": f"Created {doctype} '{doc.name}' successfully.",
    }


def _handle_get(args: dict) -> dict:
    """Get a single document."""
    doc = frappe.get_doc(args["doctype"], args["name"])
    return doc.as_dict()


def _handle_list(args: dict) -> dict:
    """List documents with filters."""
    doctype = args["doctype"]
    filters = args.get("filters", {})
    fields = args.get("fields", ["name"])
    order_by = args.get("order_by", "modified desc")
    limit = args.get("limit_page_length", 20)
    start = args.get("limit_start", 0)

    # Add common display fields if only 'name' requested
    if fields == ["name"]:
        meta = frappe.get_meta(doctype)
        if meta.title_field:
            fields.append(meta.title_field)
        fields.append("modified")

    results = frappe.get_list(
        doctype,
        filters=filters,
        fields=fields,
        order_by=order_by,
        limit_page_length=limit,
        limit_start=start,
    )

    return {
        "doctype": doctype,
        "count": len(results),
        "data": results,
    }


def _handle_update(args: dict) -> dict:
    """Update a document."""
    doc = frappe.get_doc(args["doctype"], args["name"])
    values = args.get("values", {})

    for key, value in values.items():
        doc.set(key, value)

    doc.save()
    frappe.db.commit()

    return {
        "status": "updated",
        "doctype": args["doctype"],
        "name": doc.name,
        "updated_fields": list(values.keys()),
        "message": f"Updated {args['doctype']} '{doc.name}' successfully.",
    }


def _handle_delete(args: dict) -> dict:
    """Delete a document."""
    doctype = args["doctype"]
    name = args["name"]

    frappe.delete_doc(doctype, name)
    frappe.db.commit()

    return {
        "status": "deleted",
        "doctype": doctype,
        "name": name,
        "message": f"Deleted {doctype} '{name}' successfully.",
    }


def _handle_submit(args: dict) -> dict:
    """Submit a document."""
    doc = frappe.get_doc(args["doctype"], args["name"])
    doc.submit()
    frappe.db.commit()

    return {
        "status": "submitted",
        "doctype": args["doctype"],
        "name": doc.name,
        "message": f"Submitted {args['doctype']} '{doc.name}' successfully.",
    }


def _handle_cancel(args: dict) -> dict:
    """Cancel a submitted document."""
    doc = frappe.get_doc(args["doctype"], args["name"])
    doc.cancel()
    frappe.db.commit()

    return {
        "status": "cancelled",
        "doctype": args["doctype"],
        "name": doc.name,
        "message": f"Cancelled {args['doctype']} '{doc.name}' successfully.",
    }


def _handle_report(args: dict) -> dict:
    """Run a report."""
    report_name = args["report_name"]
    filters = args.get("filters", {})
    limit = args.get("limit", 50)

    # Check if report exists
    if not frappe.db.exists("Report", report_name):
        raise frappe.DoesNotExistError(f"Report '{report_name}' does not exist")

    report = frappe.get_doc("Report", report_name)

    columns, data = report.get_data(
        filters=filters,
        limit=limit,
        as_dict=True,
    )

    return {
        "report_name": report_name,
        "columns": [c.get("label", c.get("fieldname", "")) for c in columns] if columns else [],
        "row_count": len(data) if data else 0,
        "data": data[:limit] if data else [],
    }


def _handle_count(args: dict) -> dict:
    """Count documents matching filters."""
    doctype = args["doctype"]
    filters = args.get("filters", {})

    count = frappe.db.count(doctype, filters=filters)

    return {
        "doctype": doctype,
        "count": count,
        "filters": filters,
    }
