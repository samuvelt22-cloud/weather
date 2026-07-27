import requests
import time

# Simple in-memory cache: { "city_name_lowercase": coordinates_dict }
# A city's location never changes, so this cache never expires —
# it just avoids repeat lookups for the same city and reduces API calls.
_geocode_cache = {}


def get_coordinates(city_name):
    """
    Convert a city name into latitude and longitude using Open-Meteo's
    free Geocoding API (no API key required).

    Returns a dict: {"name": str, "country": str, "latitude": float, "longitude": float}
    or None if the city could not be found / the request failed.
    """
    cache_key = city_name.strip().lower()
    if cache_key in _geocode_cache:
        print(f"[geocode.py] Using cached coordinates for '{city_name}'")
        return _geocode_cache[cache_key]

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
            print(f"[geocode.py] HTTP error from Open-Meteo: {e}")
            return None
        except requests.exceptions.RequestException as e:
            print(f"[geocode.py] Request to Open-Meteo failed: {e}")
            return None
    else:
        return None

    results = data.get("results")
    if not results:
        # City name did not match anything
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
