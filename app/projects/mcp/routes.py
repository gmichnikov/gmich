"""
MCP (Model Context Protocol) server routes.

Exposes bio tools and read-only sports schedule tools.
Endpoint: POST /mcp (JSON-RPC). GET /mcp/ renders the landing page for browsers.
"""

import json
from flask import Blueprint, request, jsonify, render_template
from app import csrf
from app.projects.mcp.sports_tools import schedule_mcp_tools
from app.projects.mcp.tools import McpToolError, TOOL_HANDLERS

mcp_bp = Blueprint(
    "mcp",
    __name__,
    template_folder="templates",
)

# MCP tool definitions for protocol
MCP_TOOLS = [
    {
        "name": "get_personal",
        "description": "Personal and family life: bio, contact, interests, family",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_work",
        "description": "Work background: skills, projects, experience",
        "inputSchema": {"type": "object", "properties": {}},
    },
] + schedule_mcp_tools()


def _handle_json_rpc(body: dict) -> dict | None:
    """Process JSON-RPC request and return response."""
    method = body.get("method")
    params = body.get("params") or {}
    req_id = body.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "gmich", "version": "0.1.0"},
            },
        }

    if method == "notifications/initialized":
        return None  # No response for notifications

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": MCP_TOOLS},
        }

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name not in TOOL_HANDLERS:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {name}"},
            }
        try:
            handler = TOOL_HANDLERS[name]
            result = handler(**args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result)}],
                    "isError": False,
                },
            }
        except McpToolError as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(e)}],
                    "isError": True,
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


@mcp_bp.route("/", methods=["GET"])
def index():
    """Landing page: how to add this MCP server as a connector."""
    return render_template("mcp/index.html")


@mcp_bp.route("/", methods=["POST"])
@csrf.exempt
def mcp_endpoint():
    """
    MCP JSON-RPC endpoint.
    Handles Initialize, tools/list, tools/call.
    """
    try:
        body = request.get_json()
        if not body:
            return jsonify({"error": "Invalid JSON"}), 400

        response = _handle_json_rpc(body)
        if response is None:
            return "", 202  # Notification — no response body

        return jsonify(response)
    except Exception as e:
        return jsonify({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}), 500
