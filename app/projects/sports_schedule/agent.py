"""ADK Agent for Sports Schedule project."""

import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent


def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city: The name of the city (e.g., "New York", "London", "Tokyo")

    Returns:
        A dict with status and either the time report or an error message.
    """
    city_timezones = {
        "new york": "America/New_York",
        "los angeles": "America/Los_Angeles",
        "chicago": "America/Chicago",
        "london": "Europe/London",
        "paris": "Europe/Paris",
        "tokyo": "Asia/Tokyo",
        "sydney": "Australia/Sydney",
    }

    tz_identifier = city_timezones.get(city.lower())
    if not tz_identifier:
        return {
            "status": "error",
            "error_message": f"Sorry, I don't have timezone information for {city}.",
        }

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    report = f'The current time in {city} is {now.strftime("%Y-%m-%d %H:%M:%S %Z")}'
    return {"status": "success", "report": report}


def add_numbers(a: int, b: int) -> dict:
    """Adds two numbers together.

    Args:
        a: The first number
        b: The second number

    Returns:
        A dict with the sum of the two numbers.
    """
    result = a + b
    return {"status": "success", "result": result, "message": f"{a} + {b} = {result}"}


# Create the agent
sports_agent = Agent(
    name="sports_schedule_agent",
    model="gemini-2.5-flash",
    description="A helpful assistant that can tell time and do math.",
    instruction="""You are a helpful assistant. You can:
1. Tell the current time in various cities using the get_current_time tool
2. Add numbers together using the add_numbers tool

When the user asks about time or wants to add numbers, use the appropriate tool.
Always be friendly and helpful in your responses.""",
    tools=[get_current_time, add_numbers],
)
