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

## 5. Debugging Tips
- Use `print(..., flush=True)` to ensure logs appear immediately in the terminal, as Flask's internal logger or standard stdout might be buffered.
- Monitor the `ADK DEBUG` logs to verify the sequence: 
    1. Session Check -> 2. Session Creation (if needed) -> 3. `run_async` Call -> 4. Event Processing.
