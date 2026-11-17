"""URLs of the app. Pages return HTML; /api/... returns JSON for the page scripts.

Every input from the URL is checked before it is used (session key and lap are
whole numbers, a driver code is three capital letters), and the raw data is
read through Parquet filters, never by building strings.
"""

import re

from flask import Blueprint, abort, current_app, jsonify, render_template, request

from app.data import HOLE_S, RawSamplesMissing

pages = Blueprint("pages", __name__)
api = Blueprint("api", __name__)

DRIVER_CODE = re.compile(r"^[A-Z]{3}$")
NAV = [("pages.home", "Overview"), ("pages.telemetry", "Lap compare"), ("pages.corners", "Corner lab"),
       ("pages.signatures", "Driver vs car"), ("pages.method", "Method")]


def data():
    """The AppData loaded once at start-up (app/__init__.py)."""
    return current_app.config["APP_DATA"]


@pages.app_context_processor
def navigation():
    """Makes the nav list available in every template (base.html draws it)."""
    return {"nav": NAV}


# ---------------------------------------------------------------- pages

@pages.route("/")
def home():
    """The overview: the replayed pole laps and the results board."""
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
    """The Corner lab, opening on the pilot session."""
    hero = data().hero
    return render_template("corners.html", active="pages.corners", default_session=hero["session_key"])


@pages.route("/signatures")
def signatures():
    """Driver vs car: H3, H4 and H5."""
    return render_template("signatures.html", active="pages.signatures")


@pages.route("/method")
def method():
    """The measurement science (sampling, filters, estimators, alignment, cleaning)."""
    return render_template("method.html", active="pages.method")


# ---------------------------------------------------------------- JSON API

@api.route("/hero")
def hero():
    """The two pole laps the overview replays (2024 Abu Dhabi)."""
    return jsonify(data().hero)


@api.route("/sessions")
def sessions():
    """Every session the app can show, for the season and session pickers."""
    return jsonify(data().session_index())


@api.route("/sessions/<int:key>")
def session(key):
    """One session's drivers, laps and corners; 404 for an unknown key. raw_available says whether
    the local raw samples of that season exist (Lap compare needs them)."""
    if key not in data().sessions:
        abort(404)
    session = data().sessions[key]
    return jsonify({**session, "raw_available": data().raw_available(session["year"]), "hole_threshold_s": HOLE_S})


def parse_lap(text):
    """'NOR:15' -> ('NOR', 15); anything else -> 400 Bad Request."""
    parts = (text or "").split(":")
    if len(parts) != 2 or not DRIVER_CODE.match(parts[0]) or not parts[1].isdigit():
        abort(400, description="lap must look like NOR:15")
    return parts[0], int(parts[1])


@api.route("/compare/<int:key>")
def compare(key):
    """Two laps of one session on one distance axis, with the gap between them
    (?a=NOR:15&b=PIA:12). 400 for a malformed lap, 404 for an unknown session or lap, 503 with a
    hint if the raw samples were never built."""
    if key not in data().sessions:
        abort(404)
    a = parse_lap(request.args.get("a"))
    b = parse_lap(request.args.get("b"))
    try:
        result = data().compare(key, a, b)
    except RawSamplesMissing as missing:
        return jsonify({"error": "raw samples not built",
                        "hint": f"results/{missing} is missing: run experiments/09_build_dataset.py "
                                f"(2023-2024); for 2025 and 2026 keep the local files of the one-time tests "
                                f"(results/final/, results/final_2026/)."}), 503
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
    """The feature table (errors and repeatability per corner type)."""
    return export_or_503(data().features, "features.json")


@api.route("/identification")
def identification():
    """The H3 results per team-season."""
    return export_or_503(data().identification, "identification.json")


@api.route("/signatures")
def signature_data():
    """The H4 signatures and distances."""
    return export_or_503(data().signatures, "signatures.json")


@api.route("/h5")
def h5_data():
    """The frozen 2026 test (H5)."""
    return export_or_503(data().h5, "h5.json")


@api.route("/method")
def method_data():
    """The measurement-science charts of the Method page."""
    return export_or_503(data().method, "method.json")


@api.route("/corners/<int:key>")
def corner_rows(key):
    """Every clean corner pass of one session (Corner lab); 503 with a hint if the dataset is missing."""
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
    """API errors as JSON ({"error": ...}) instead of an HTML page, so the page scripts can show them."""
    return jsonify({"error": error.description}), error.code
