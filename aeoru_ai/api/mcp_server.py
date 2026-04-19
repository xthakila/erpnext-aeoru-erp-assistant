#!/usr/bin/env python3
"""MCP Server for ERPNext — exposes Frappe document tools to Claude Code CLI.

Runs as a stdio-based MCP server. Claude Code connects to it via:
  --mcp-server "frappe:/path/to/mcp_runner.sh"

Uses the FastMCP library (bundled with anthropic SDK).
"""
import json
import sys
import os

# Frappe must be initialized before any tool calls
import frappe

def init_frappe():
    """Initialize Frappe context for the MCP server process."""
    site = os.environ.get("FRAPPE_SITE", "dev.localhost")
    bench_dir = os.environ.get("BENCH_DIR", "/home/frappe/frappe-bench")
    # Frappe expects cwd to be the sites directory
    os.chdir(os.path.join(bench_dir, "sites"))
    frappe.init(site=site)
    frappe.connect()
    frappe.set_user("Administrator")


def main():
    """Run the MCP server using JSON-RPC over stdio."""
    init_frappe()

    from aeoru_ai.api.tools.definitions import ALL_TOOLS
    from aeoru_ai.api.tools.executor import execute_tool
    from aeoru_ai.api.providers.base import ToolCall

    # Build tool list in MCP format
    mcp_tools = {}
    for tool in ALL_TOOLS:
        mcp_tools[tool["name"]] = {
            "description": tool["description"],
            "inputSchema": {
                "type": "object",
                "properties": tool["parameters"].get("properties", {}),
                "required": tool["parameters"].get("required", []),
            },
        }

    def handle_request(request):
        """Handle a single JSON-RPC request."""
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {
                        "name": "frappe-erpnext",
                        "version": "1.0.0",
                    },
                },
            }

        elif method == "notifications/initialized":
            # No response needed for notifications
            return None

        elif method == "tools/list":
            tools_list = []
            for name, spec in mcp_tools.items():
                tools_list.append({
                    "name": name,
                    "description": spec["description"],
                    "inputSchema": spec["inputSchema"],
                })
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": tools_list},
            }

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})

            if tool_name not in mcp_tools:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                        "isError": True,
                    },
                }

            # Execute using our existing tool executor
            tool_call = ToolCall(id=str(req_id), name=tool_name, arguments=tool_args)
            result = execute_tool(tool_call, confirmed=True)

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result.content}],
                    "isError": result.is_error,
                },
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }

    # Main loop: read JSON-RPC messages from stdin, write responses to stdout
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        response = handle_request(request)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
