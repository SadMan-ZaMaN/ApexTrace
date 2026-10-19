"""URLs of the app. Pages return HTML; /api/... returns JSON for the page scripts.

Every input from the URL is checked before it is used (session key and lap are
whole numbers, a driver code is three capital letters), and the raw data is
read through Parquet filters, never by building strings.
"""

import re

from flask import Blueprint, abort, current_app, jsonify, render_template, request

from app.data import RawSamplesMissing

pages = Blueprint("pages", __name__)
api = Blueprint("api", __name__)

DRIVER_CODE = re.compile(r"^[A-Z]{3}$")
NAV = [("pages.home", "Overview"), ("pages.telemetry", "Lap compare"), ("pages.corners", "Corner lab"),
       ("pages.signatures", "Driver vs car")]


def data():
    return current_app.config["APP_DATA"]


@pages.app_context_processor
def navigation():
    """Makes the nav list available in every template (base.html draws it)."""
    return {"nav": NAV}


# ---------------------------------------------------------------- pages

@pages.route("/")
def home():
    return render_template("index.html", headline=data().headline, active="pages.home")


@pages.route("/telemetry")
def telemetry():
    """Opens on the pilot comparison (the hero laps) unless the URL asks for another."""
    hero = data().hero
    a, b = hero["cars"][0], hero["cars"][1]
    return render_template("telemetry.html", active="pages.telemetry",
                           default_session=hero["session_key"],
                           default_a=f"{a['code']}:{a['lap']}", default_b=f"{b['code']}:{b['lap']}",
                           alignment_error_m=data().headline["data"]["alignment_error_m"])


@pages.route("/corners")
def corners():
    hero = data().hero
    return render_template("corners.html", active="pages.corners", default_session=hero["session_key"])


@pages.route("/signatures")
def signatures():
    return render_template("signatures.html", active="pages.signatures")


# ---------------------------------------------------------------- JSON API

@api.route("/hero")
def hero():
    return jsonify(data().hero)


@api.route("/sessions")
def sessions():
    return jsonify(data().session_index())


@api.route("/sessions/<int:key>")
def session(key):
    if key not in data().sessions:
        abort(404)
    session = data().sessions[key]
    return jsonify({**session, "raw_available": data().raw_available(session["year"])})


def parse_lap(text):
    """'NOR:15' -> ('NOR', 15); anything else -> 400 Bad Request."""
    parts = (text or "").split(":")
    if len(parts) != 2 or not DRIVER_CODE.match(parts[0]) or not parts[1].isdigit():
        abort(400, description="lap must look like NOR:15")
    return parts[0], int(parts[1])


@api.route("/compare/<int:key>")
def compare(key):
    if key not in data().sessions:
        abort(404)
    a = parse_lap(request.args.get("a"))
    b = parse_lap(request.args.get("b"))
    try:
        result = data().compare(key, a, b)
    except RawSamplesMissing as missing:
        return jsonify({"error": "raw samples not built",
                        "hint": f"results/{missing} is missing: run experiments/09_build_dataset.py "
                                f"(2023-2024) or keep results/final/ (2025)."}), 503
    if result is None:
        abort(404, description="no samples for that lap")
    return jsonify(result)


def export_or_503(content, name):
    """An optional export file, or a 503 telling how to create it."""
    if content is None:
        return jsonify({"error": f"results/app/{name} is missing",
                        "hint": "run experiments/16_app_data.py"}), 503
    return jsonify(content)


@api.route("/features")
def features():
    return export_or_503(data().features, "features.json")


@api.route("/identification")
def identification():
    return export_or_503(data().identification, "identification.json")


@api.route("/signatures")
def signature_data():
    return export_or_503(data().signatures, "signatures.json")


@api.route("/corners/<int:key>")
def corner_rows(key):
    if key not in data().sessions:
        abort(404)
    rows = data().corner_rows(key)
    if rows is None:
        return jsonify({"error": "dataset files missing",
                        "hint": "results/09_dataset/dataset.csv.gz is committed; pull the repository again"}), 503
    return jsonify({"session_key": key, "rows": rows})


@api.errorhandler(400)
@api.errorhandler(404)
def json_error(error):
    return jsonify({"error": error.description}), error.code
