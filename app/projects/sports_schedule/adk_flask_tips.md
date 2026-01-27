# Google ADK + Flask Integration Tips

This document summarizes key learnings and patterns for integrating the Google Agent Development Kit (ADK) with a Flask web application.

## 1. Session Management (Crucial)
The `InMemoryRunner` is strict: it will throw a `ValueError: Session not found` if you attempt to run an agent with a `session_id` that hasn't been explicitly created.

### The "Get or Create" Pattern
Always ensure the session exists before calling `run_async`. Web apps are stateless, so you must handle session initialization on the first request from a user.

```python
async def run_agent(user_id: str, session_id: str, message: str):
    # Ensure session exists in the runner's memory service
    try:
        await runner.session_service.get_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id
        )
    except Exception:
        # Create session if get_session fails or returns None
        await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id
        )
    
    # Now it is safe to run
    async for event in runner.run_async(...):
        # ...
```

## 2. App Name Synchronization
The `app_name` acts as a namespace for sessions. If the `Runner` and `session_service` calls use different names, they won't find each other's data.
- **Best Practice**: Use `runner = InMemoryRunner(agent=my_agent, app_name=my_agent.name)` and always reference `runner.app_name` in session calls.

## 3. Handling Async in Flask
Flask is typically synchronous, while ADK is natively asynchronous.
- Use `asyncio.run(run_agent(...))` in your Flask route to bridge the gap.
- Note that `asyncio.run()` creates a new event loop per request. This works with `InMemoryRunner` as long as the runner instance itself is persistent (e.g., defined at the module level).

## 4. Dependencies
The `google-adk` package may have implicit dependencies that aren't always installed automatically depending on your environment.
- Ensure `deprecated`, `pydantic`, and `google-genai` are in your `requirements.txt`.

## 6. Real-time Streaming (Step-by-Step)
To show tool calls and partial text as they happen, use Server-Sent Events (SSE). 

### The Threaded Queue Pattern
Since Flask is synchronous and ADK is async, the most robust way to stream is to run the ADK loop in a separate thread and communicate via a `queue.Queue`.

```python
def generate():
    import queue
    import threading
    q = queue.Queue()

    def run_async_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        async def run_it():
            try:
                # 1. Ensure Session (same loop as run_async)
                # 2. async for event in runner.run_async(...)
                # 3. q.put(json_payload)
            finally:
                q.put(None) # Signal end
        loop.run_until_complete(run_it())

    threading.Thread(target=run_async_loop).start()
    while True:
        item = q.get()
        if item is None: break
        yield f"data: {item}\n\n"
```

### Parsing Events
The `Event` object from ADK contains different fields depending on the step:
- **Tool Calls**: `event.get_function_calls()`
- **Tool Responses**: `event.get_function_responses()`
- **Text**: `event.content.parts` (look for `.text` attribute)

## 8. Using Built-in Tools (Google Search, etc.)
The Gemini API has a limitation: you cannot mix "Built-in" tools (like `google_search`) with "Function Calling" (like `transfer_to_agent`, `escalate`, or custom Python tools) in the same agent request.

### The AgentTool Pattern
To use `google_search` in a multi-agent system, wrap it in an `AgentTool`. This isolates the built-in tool from the manager's orchestration logic.

```python
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool

# 1. Create a specialist with ONLY the built-in tool
search_agent = Agent(
    name="search_specialist",
    tools=[google_search],
    instruction="Use google_search to find facts and state them."
)

# 2. Wrap it as a tool
search_tool = AgentTool(agent=search_agent)

# 3. Add the WRAPPED tool to the Manager's tools list (NOT sub_agents)
manager = Agent(
    name="manager",
    tools=[search_tool],
    sub_agents=[other_agents],
    instruction="Call the search_specialist tool for web info."
)
```

## 9. Orchestration Patterns (Hub-and-Spoke)
For complex multi-step tasks, the **Hub-and-Spoke** (or Star) pattern is generally more stable than a decentralized "Mesh."

### Key Principles:
1. **Central Control**: Only the Manager (Hub) is allowed to delegate tasks (using `transfer_to_agent`).
2. **Specialist Autonomy**: Specialists (Spokes) focus strictly on their one job.
3. **Always Return**: Specialists are instructed to use the `escalate` tool immediately after providing their data, handing control back to the Manager.
4. **Final Synthesis**: The Manager is responsible for collecting all gathered data from the history and providing the final summary to the user.

## 10. Debugging Tips
- Use `print(..., flush=True)` to ensure logs appear immediately in the terminal, as Flask's internal logger or standard stdout might be buffered.
- Monitor the `ADK DEBUG` logs to verify the sequence: 
    1. Session Check -> 2. Session Creation (if needed) -> 3. `run_async` Call -> 4. Event Processing.
