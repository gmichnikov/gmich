"""
MCP (Model Context Protocol) server routes.

Two connectors on one app. POST /mcp is the personal bio. POST /mcp/sports is
read-only schedule search. GET on either URL renders the landing page.
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

PERSONAL_TOOLS = [
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
]
SPORTS_TOOLS = schedule_mcp_tools()


def _handle_json_rpc(body: dict, tools: list[dict], server_name: str) -> dict | None:
    """Process JSON-RPC request and return response."""
    method = body.get("method")
    params = body.get("params") or {}
    req_id = body.get("id")
    allowed = {tool["name"] for tool in tools}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": server_name, "version": "0.1.0"},
            },
        }

    if method == "notifications/initialized":
        return None  # No response for notifications

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tools},
        }

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        if name not in allowed or name not in TOOL_HANDLERS:
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


def _landing_page():
    return render_template("mcp/index.html")


def _json_rpc_response(tools: list[dict], server_name: str):
    try:
        body = request.get_json()
        if not body:
            return jsonify({"error": "Invalid JSON"}), 400

        response = _handle_json_rpc(body, tools, server_name)
        if response is None:
            return "", 202  # Notification — no response body

        return jsonify(response)
    except Exception as e:
        return jsonify({"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}}), 500


@mcp_bp.route("/", methods=["GET"])
def index():
    """Landing page: how to add either connector."""
    return _landing_page()


@mcp_bp.route("/", methods=["POST"])
@csrf.exempt
def mcp_endpoint():
    """Personal bio connector. Handles initialize, tools/list, and tools/call."""
    return _json_rpc_response(PERSONAL_TOOLS, "gmich")


@mcp_bp.route("/sports", methods=["GET"], strict_slashes=False)
def sports_index():
    """Same landing page. Browsers that open the sports URL still see both connectors."""
    return _landing_page()


@mcp_bp.route("/sports", methods=["POST"], strict_slashes=False)
@csrf.exempt
def sports_endpoint():
    """Sports schedule connector. Handles initialize, tools/list, and tools/call."""
    return _json_rpc_response(SPORTS_TOOLS, "gmich-sports")
