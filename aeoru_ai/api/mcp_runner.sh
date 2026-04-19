#!/bin/bash
# MCP Runner for Frappe ERPNext tools
# Called by Claude Code via --mcp-server "frappe:/path/to/mcp_runner.sh"

BENCH_DIR="/home/frappe/frappe-bench"
cd "$BENCH_DIR"

# Activate the bench virtual environment
source env/bin/activate

# Ensure currentsite.txt exists (Frappe needs it)
export FRAPPE_SITE="${FRAPPE_SITE:-dev.localhost}"
echo "$FRAPPE_SITE" > sites/currentsite.txt 2>/dev/null || true

# Run the MCP server
exec python -m aeoru_ai.api.mcp_server
