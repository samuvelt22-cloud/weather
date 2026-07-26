import requests
from datetime import datetime

# Maps Open-Meteo's WMO weather codes to a human-readable description
# and an icon filename. Add matching images inside static/images/
# with these exact filenames (e.g. static/images/sunny.png).
WEATHER_CODES = {
    0: ("Clear sky", "sunny.png"),
    1: ("Mainly clear", "sunny.png"),
    2: ("Partly cloudy", "cloudy.png"),
    3: ("Overcast", "cloudy.png"),
    45: ("Fog", "fog.png"),
    48: ("Depositing rime fog", "fog.png"),
    51: ("Light drizzle", "rain.png"),
    53: ("Moderate drizzle", "rain.png"),
    55: ("Dense drizzle", "rain.png"),
    61: ("Slight rain", "rain.png"),
    63: ("Moderate rain", "rain.png"),
    65: ("Heavy rain", "rain.png"),
    71: ("Slight snow fall", "snow.png"),
    73: ("Moderate snow fall", "snow.png"),
    75: ("Heavy snow fall", "snow.png"),
    80: ("Slight rain showers", "rain.png"),
    81: ("Moderate rain showers", "rain.png"),
    82: ("Violent rain showers", "rain.png"),
    95: ("Thunderstorm", "storm.png"),
    96: ("Thunderstorm with hail", "storm.png"),
    99: ("Thunderstorm with heavy hail", "storm.png"),
}

DEFAULT_CONDITION = ("Unknown", "cloudy.png")


def _describe(code):
    """Look up a WMO weather code, falling back to a default if unknown."""
    return WEATHER_CODES.get(code, DEFAULT_CONDITION)


def _format_time(iso_string):
    """Turn '2026-07-26T05:52' into '05:52 AM' for easier reading."""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%I:%M %p")
    except (ValueError, TypeError):
        return iso_string


def _format_day(date_string):
    """Turn '2026-07-27' into 'Mon' for forecast cards."""
    try:
        dt = datetime.strptime(date_string, "%Y-%m-%d")
        return dt.strftime("%a")
    except ValueError:
        return date_string


def get_weather(latitude, longitude, city_name):
    """
    Fetch current weather and a 5-day forecast from Open-Meteo
    (no API key required) and return dicts shaped for the Jinja2 templates.

    Returns (weather_dict, forecast_list) on success, or (None, None) on failure.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset",
        "timezone": "auto",
        "forecast_days": 6
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"[weather.py] Request to Open-Meteo failed: {e}")
        return None, None

    current = data.get("current")
    daily = data.get("daily")

    if not current or not daily:
        print(f"[weather.py] Unexpected API response, missing current/daily: {data}")
        return None, None

    condition, icon = _describe(current.get("weather_code"))

    weather = {
        "city": city_name,
        "temperature": round(current.get("temperature_2m", 0)),
        "feels_like": round(current.get("apparent_temperature", 0)),
        "condition": condition,
        "icon": f"/static/images/{icon}",
        "humidity": current.get("relative_humidity_2m"),
        "wind_speed": current.get("wind_speed_10m"),
        "sunrise": _format_time(daily["sunrise"][0]),
        "sunset": _format_time(daily["sunset"][0])
    }

    forecast = []
    # Skip index 0 (today, already shown above) and list the next 5 days.
    for i in range(1, min(6, len(daily["time"]))):
        day_condition, day_icon = _describe(daily["weather_code"][i])
        forecast.append({
            "day": _format_day(daily["time"][i]),
            "icon": f"/static/images/{day_icon}",
            "min_temp": round(daily["temperature_2m_min"][i]),
            "max_temp": round(daily["temperature_2m_max"][i]),
            "description": day_condition
        })

    return weather, forecast
