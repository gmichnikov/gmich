"""
MCP (Model Context Protocol) server routes.

Exposes a personal bio/résumé as queryable tools for AI assistants.
Endpoint: POST /mcp (JSON-RPC), GET /mcp (landing page or 405 for MCP clients).
"""

import json
from flask import Blueprint, request, jsonify, render_template, Response
from app import csrf
from app.projects.mcp.tools import TOOL_HANDLERS

mcp_bp = Blueprint(
    "mcp",
    __name__,
    template_folder="templates",
)

# MCP tool definitions for protocol
MCP_TOOLS = [
    {
        "name": "get_bio",
        "description": "Short and long biography",
        "inputSchema": {
            "type": "object",
            "properties": {"short": {"type": "boolean", "default": True}},
        },
    },
    {
        "name": "get_skills",
        "description": "Technical and professional skills",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_projects",
        "description": "Portfolio projects with links, stack, outcomes",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_experience",
        "description": "Work history",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_contact",
        "description": "Contact info and socials",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_resume",
        "description": "Full structured résumé",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "answer_question",
        "description": "Freeform Q&A about you, powered by Claude with your data as context",
        "inputSchema": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
]


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
                "serverInfo": {"name": "mcp-bio", "version": "0.1.0"},
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
