"""ADK Agent for Sports Schedule project."""

import datetime
import requests
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


def get_weather(city: str) -> dict:
    """Returns the current weather in a specified city.

    Args:
        city: The name of the city (e.g., "New York", "London", "Tokyo")

    Returns:
        A dict with status and either the weather report or an error message.
    """
    try:
        # 1. Geocoding: Get lat/long for the city
        geocoding_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
        geo_response = requests.get(geocoding_url)
        geo_data = geo_response.json()

        if not geo_data.get("results"):
            return {
                "status": "error",
                "error_message": f"Could not find coordinates for {city}.",
            }

        result = geo_data["results"][0]
        lat, lon = result["latitude"], result["longitude"]
        full_name = f"{result.get('name')}, {result.get('country')}"

        # 2. Weather: Get current weather using coordinates
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code"
        weather_response = requests.get(weather_url)
        weather_data = weather_response.json()

        if "current" not in weather_data:
            return {
                "status": "error",
                "error_message": f"Could not fetch weather for {city}.",
            }

        temp = weather_data["current"]["temperature_2m"]
        code = weather_data["current"]["weather_code"]

        # Simple mapping for common weather codes
        descriptions = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            61: "Slight rain",
            71: "Slight snow fall",
            80: "Slight rain showers",
            95: "Thunderstorm",
        }
        desc = descriptions.get(code, "Unknown")

        report = f"The current weather in {full_name} is {desc} with a temperature of {temp}°C."
        return {"status": "success", "report": report, "temperature_c": temp}

    except Exception as e:
        return {"status": "error", "error_message": str(e)}


def convert_c_to_f(celsius: float) -> dict:
    """Converts a temperature from Celsius to Fahrenheit.

    Args:
        celsius: The temperature in degrees Celsius.

    Returns:
        A dict with the temperature in Fahrenheit.
    """
    fahrenheit = (celsius * 9 / 5) + 32
    return {
        "status": "success",
        "celsius": celsius,
        "fahrenheit": fahrenheit,
        "message": f"{celsius}°C is equal to {fahrenheit:.1f}°F",
    }


# Create the agent
sports_agent = Agent(
    name="sports_schedule_agent",
    model="gemini-2.5-flash",
    description="A helpful assistant that can tell time, do math, and check weather.",
    instruction="""You are a helpful assistant. You can:
1. Tell the current time in various cities using the get_current_time tool
2. Add numbers together using the add_numbers tool
3. Check the weather in various cities using the get_weather tool
4. Convert Celsius to Fahrenheit using the convert_c_to_f tool

When the user asks about time, weather, or wants to add numbers, use the appropriate tool.
If a user asks for a temperature in Fahrenheit, first get the weather (which provides Celsius) and then use the convert_c_to_f tool to provide the conversion. Only perform the conversion if specifically requested by the user.

Always be friendly and helpful in your responses.""",
    tools=[get_current_time, add_numbers, get_weather, convert_c_to_f],
)
