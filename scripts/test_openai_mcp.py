#!/usr/bin/env python3
"""Check whether OpenAI's Responses API can import tools from an MCP connector.

Uses OPENAI_API_KEY from the environment or the project .env. Stdlib plus
python-dotenv, which this repo already has.

  python3 scripts/test_openai_mcp.py https://gregmichnikov.com/mcp/sports
  python3 scripts/test_openai_mcp.py https://gregmichnikov.com/mcp/sports --call "What games are in NJ this weekend?"

Step 1 (default): OpenAI fetches the tool list. An mcp_list_tools item means
their client finished initialize and tools/list against the server.
Step 2 (--call PROMPT): also lets the model call a tool (require_approval=never).
"""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MODEL = "gpt-6.1-terra"
DEFAULT_URL = "https://gregmichnikov.com/mcp/sports"


def main() -> int:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    args = sys.argv[1:]
    url = DEFAULT_URL
    prompt = "Reply with the single word OK."
    call_prompt = None
    if "--call" in args:
        i = args.index("--call")
        if i + 1 >= len(args):
            print("--call needs a prompt.")
            return 2
        call_prompt = args[i + 1]
        prompt = call_prompt
    for arg in args:
        if arg.startswith("--") or arg == call_prompt:
            continue
        url = arg
        break

    key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
    if not key:
        print("Set OPENAI_API_KEY, or put it in the project .env.")
        return 2

    body = {
        "model": model,
        "input": prompt,
        "tools": [
            {
                "type": "mcp",
                "server_label": "gmich",
                "server_url": url,
                "require_approval": "never",
            }
        ],
    }
    print(f"model: {model}")
    print(f"server: {url}")
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code} from OpenAI:\n{exc.read().decode(errors='replace')}")
        return 1

    items = data.get("output", [])
    listed = [item for item in items if item.get("type") == "mcp_list_tools"]
    calls = [item for item in items if item.get("type") in ("mcp_call", "mcp_tool_call")]

    print(f"output item types: {[item.get('type') for item in items]}")
    if not listed:
        print("\nFAIL or inconclusive: no mcp_list_tools item. Full response:")
        print(json.dumps(data, indent=2)[:4000])
        return 1

    tools = listed[0].get("tools", [])
    print(f"\nPASS: tool import worked. {len(tools)} tool(s):")
    for tool in tools:
        print(f"  - {tool.get('name')}")
    if listed[0].get("error"):
        print(f"  (list item error: {listed[0]['error']})")

    for call in calls:
        print(f"\ntool call: {call.get('name')} args={call.get('arguments')}")
        print(f"  error: {call.get('error')}")
        print(f"  output: {str(call.get('output'))[:500]}")
    if data.get("output_text"):
        print(f"\nmodel said: {data['output_text']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
