import frappe


def get_doctype_fields(doctype: str, include_hidden: bool = False) -> list:
    """Get filtered field list for a DocType.

    Returns fields with: fieldname, label, fieldtype, reqd, options, default
    Excludes internal fields (amended_from, column_break, etc.) unless include_hidden=True.
    """
    meta = frappe.get_meta(doctype)

    skip_fieldtypes = {"Column Break", "Section Break", "Tab Break", "HTML", "Fold"}
    skip_fieldnames = {"amended_from", "naming_series"}

    fields = []
    for f in meta.fields:
        if not include_hidden:
            if f.fieldtype in skip_fieldtypes:
                continue
            if f.fieldname in skip_fieldnames:
                continue
            if f.hidden:
                continue

        field_info = {
            "fieldname": f.fieldname,
            "label": f.label or f.fieldname,
            "fieldtype": f.fieldtype,
            "reqd": f.reqd,
        }

        if f.options:
            field_info["options"] = f.options
        if f.default:
            field_info["default"] = f.default
        if f.fieldtype == "Link":
            field_info["linked_to"] = f.options
        if f.fieldtype == "Select" and f.options:
            field_info["select_options"] = f.options.split("\n")

        fields.append(field_info)

    return fields


def get_required_fields(doctype: str) -> list:
    """Get only required fields for a DocType."""
    all_fields = get_doctype_fields(doctype)
    return [f for f in all_fields if f.get("reqd")]


def get_doctype_info(doctype: str) -> dict:
    """Get comprehensive DocType information for AI context."""
    meta = frappe.get_meta(doctype)

    return {
        "doctype": doctype,
        "module": meta.module,
        "is_submittable": bool(meta.is_submittable),
        "is_tree": bool(meta.is_tree),
        "is_single": bool(meta.issingle),
        "title_field": meta.title_field,
        "search_fields": meta.search_fields,
        "fields": get_doctype_fields(doctype),
        "required_fields": get_required_fields(doctype),
    }
