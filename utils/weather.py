import os
import requests
import time
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

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

OPENWEATHER_ICON_MAP = {
    "01": "sunny.png",
    "02": "cloudy.png",
    "03": "cloudy.png",
    "04": "cloudy.png",
    "09": "rain.png",
    "10": "rain.png",
    "11": "storm.png",
    "13": "snow.png",
    "50": "fog.png",
}

# Simple in-memory cache: { "lat,lon": (timestamp, weather_dict, forecast_list) }
# Avoids repeat API calls for the same location within CACHE_SECONDS,
# which reduces how often we hit Open-Meteo's rate limit.
_weather_cache = {}
CACHE_SECONDS = 600  # 10 minutes


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


def _openweather_icon(weather_list):
    if not weather_list:
        return "cloudy.png"
    icon_code = weather_list[0].get("icon", "")
    return OPENWEATHER_ICON_MAP.get(icon_code[:2], "cloudy.png")


def _format_unix_time(timestamp):
    try:
        return datetime.fromtimestamp(timestamp).strftime("%I:%M %p")
    except (TypeError, OSError, OverflowError):
        return str(timestamp)


def _fetch_openweather(latitude, longitude):
    url = "https://api.openweathermap.org/data/2.5/onecall"
    params = {
        "lat": latitude,
        "lon": longitude,
        "units": "metric",
        "exclude": "minutely,hourly,alerts",
        "appid": OPENWEATHER_API_KEY,
        "lang": "en",
    }

    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 and attempt < 2:
                wait = 2 * (attempt + 1)
                print(f"[weather.py] OpenWeather rate limited, retrying in {wait} seconds...")
                time.sleep(wait)
                continue
            print(f"[weather.py] HTTP error from OpenWeather: {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[weather.py] Request to OpenWeather failed: {e}")
            return None
    return None


def _fetch_open_meteo(latitude, longitude):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset",
        "timezone": "auto",
        "forecast_days": 6
    }

    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 and attempt < 2:
                wait = 2 * (attempt + 1)
                print(f"[weather.py] Open-Meteo rate limited, retrying in {wait} seconds...")
                time.sleep(wait)
                continue
            print(f"[weather.py] HTTP error from Open-Meteo: {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[weather.py] Request to Open-Meteo failed: {e}")
            return None
    return None


def get_weather(latitude, longitude, city_name):
    """
    Fetch current weather and a 5-day forecast from OpenWeather (if an API key is set)
    or from Open-Meteo as a fallback. Returns dicts shaped for the Jinja2 templates.

    Returns (weather_dict, forecast_list) on success, or (None, None) on failure.
    """
    cache_key = f"{round(latitude, 2)},{round(longitude, 2)}"
    cached = _weather_cache.get(cache_key)
    if cached and (time.time() - cached[0]) < CACHE_SECONDS:
        print(f"[weather.py] Using cached weather for {cache_key}")
        weather, forecast = cached[1], cached[2]
        weather = dict(weather)  # copy so we can set the current city name
        weather["city"] = city_name
        return weather, forecast

    data = None
    if OPENWEATHER_API_KEY:
        data = _fetch_openweather(latitude, longitude)
        if data is None:
            print("[weather.py] Falling back to Open-Meteo because OpenWeather request failed.")

    if data is None:
        data = _fetch_open_meteo(latitude, longitude)

    if data is None:
        return None, None

    current = data.get("current")
    daily = data.get("daily")

    if not current or not daily:
        print(f"[weather.py] Unexpected API response, missing current/daily: {data}")
        return None, None

    if current.get("weather"):
        current_weather = current["weather"]
        condition = current_weather[0].get("description", "Unknown").title()
        icon = _openweather_icon(current_weather)

        weather = {
            "city": city_name,
            "temperature": round(current.get("temp", 0)),
            "feels_like": round(current.get("feels_like", 0)),
            "condition": condition,
            "icon": f"/static/images/{icon}",
            "humidity": current.get("humidity"),
            "wind_speed": current.get("wind_speed"),
            "sunrise": _format_unix_time(current.get("sunrise")),
            "sunset": _format_unix_time(current.get("sunset"))
        }

        forecast = []
        for daily_item in daily[1:min(6, len(daily))]:
            day_weather = daily_item.get("weather", [])
            forecast.append({
                "day": _format_day(daily_item.get("dt", "")),
                "icon": f"/static/images/{_openweather_icon(day_weather)}",
                "min_temp": round(daily_item.get("temp", {}).get("min", 0)),
                "max_temp": round(daily_item.get("temp", {}).get("max", 0)),
                "description": day_weather[0].get("description", "Unknown").title() if day_weather else "Unknown"
            })
    else:
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

    _weather_cache[cache_key] = (time.time(), weather, forecast)
    return weather, forecast
