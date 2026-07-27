import os
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, request

from utils.geocode import get_coordinates
from utils.weather import get_weather

app = Flask(__name__)


@app.route("/home", methods=["GET", "POST"])
def index():
    weather = None
    forecast = None
    error = None

    if request.method == "POST":
        city = request.form.get("city", "").strip()

        if not city:
            error = "Please enter a city name."
        else:
            location = get_coordinates(city)

            if location is None:
                error = f"Sorry, we couldn't find a place called '{city}'."
            else:
                weather, forecast = get_weather(
                    location["latitude"],
                    location["longitude"],
                    f"{location['name']}, {location['country']}"
                )

                if weather is None:
                    error = "Sorry, the weather service is unavailable right now. Please try again later."

    return render_template("index.html", weather=weather, forecast=forecast, error=error)


@app.route("/")
def about():
    return render_template("about.html")


@app.errorhandler(404)
def page_not_found(e):
    return render_template("error.html", error="That page doesn't exist."), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", error="Something went wrong on our end."), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
