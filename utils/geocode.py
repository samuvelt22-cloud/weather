import requests


def get_coordinates(city_name):
    """
    Convert a city name into latitude and longitude using Open-Meteo's
    free Geocoding API (no API key required).

    Returns a dict: {"name": str, "country": str, "latitude": float, "longitude": float}
    or None if the city could not be found / the request failed.
    """
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city_name,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException:
        # Network error, timeout, or bad response from the API
        return None

    results = data.get("results")
    if not results:
        # City name did not match anything
        return None

    place = results[0]

    return {
        "name": place.get("name"),
        "country": place.get("country"),
        "latitude": place.get("latitude"),
        "longitude": place.get("longitude")
    }
