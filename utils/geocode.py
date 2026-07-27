import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

# Simple in-memory cache: { "city_name_lowercase": coordinates_dict }
# A city's location never changes, so this cache never expires —
# it just avoids repeat lookups for the same city and reduces API calls.
_geocode_cache = {}


def get_coordinates(city_name):
    """
    Convert a city name into latitude and longitude using OpenWeather's
    geocoding API when an API key is configured, or Open-Meteo otherwise.

    Returns a dict: {"name": str, "country": str, "latitude": float, "longitude": float}
    or None if the city could not be found / the request failed.
    """
    cache_key = city_name.strip().lower()
    if cache_key in _geocode_cache:
        print(f"[geocode.py] Using cached coordinates for '{city_name}'")
        return _geocode_cache[cache_key]

    if OPENWEATHER_API_KEY:
        url = "http://api.openweathermap.org/geo/1.0/direct"
        params = {
            "q": city_name,
            "limit": 1,
            "appid": OPENWEATHER_API_KEY
        }
    else:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {
            "name": city_name,
            "count": 1,
            "language": "en",
            "format": "json"
        }

    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            break
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 and attempt < 2:
                wait = 2 * (attempt + 1)
                print(f"[geocode.py] Rate limited, retrying in {wait} seconds...")
                time.sleep(wait)
                continue
            source = "OpenWeather" if OPENWEATHER_API_KEY else "Open-Meteo"
            print(f"[geocode.py] HTTP error from {source}: {e}")
            if OPENWEATHER_API_KEY:
                print("[geocode.py] Falling back to Open-Meteo geocoding.")
                return _fallback_open_meteo(city_name, cache_key)
            return None
        except requests.exceptions.RequestException as e:
            source = "OpenWeather" if OPENWEATHER_API_KEY else "Open-Meteo"
            print(f"[geocode.py] Request to {source} failed: {e}")
            if OPENWEATHER_API_KEY:
                print("[geocode.py] Falling back to Open-Meteo geocoding.")
                return _fallback_open_meteo(city_name, cache_key)
            return None
    else:
        return None

    results = data if OPENWEATHER_API_KEY else data.get("results")
    if not results:
        # City name did not match anything
        if OPENWEATHER_API_KEY:
            return _fallback_open_meteo(city_name, cache_key)
        return None

    place = results[0]

    location = {
        "name": place.get("name"),
        "country": place.get("country", ""),
        "latitude": place.get("lat") if OPENWEATHER_API_KEY else place.get("latitude"),
        "longitude": place.get("lon") if OPENWEATHER_API_KEY else place.get("longitude")
    }

    _geocode_cache[cache_key] = location
    return location


def _fallback_open_meteo(city_name, cache_key):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city_name,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()
            break
        except requests.exceptions.RequestException as e:
            if attempt < 2:
                wait = 2 * (attempt + 1)
                print(f"[geocode.py] Open-Meteo geocoding failed, retrying in {wait} seconds...: {e}")
                time.sleep(wait)
                continue
            print(f"[geocode.py] Open-Meteo geocoding failed: {e}")
            return None
    else:
        return None

    results = data.get("results")
    if not results:
        return None

    place = results[0]
    location = {
        "name": place.get("name"),
        "country": place.get("country"),
        "latitude": place.get("latitude"),
        "longitude": place.get("longitude")
    }

    _geocode_cache[cache_key] = location
    return location
