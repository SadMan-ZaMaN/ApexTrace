"""ApexTrace web app (Phase 8): Flask serves the pages and a small JSON API.

Layout (the classic Flask "application factory" pattern):
  app/__init__.py   create_app(): builds the Flask object, loads the data once
  app/__main__.py   `python -m app` starts the local server
  app/data.py       where every number comes from (results/app/*.json + raw laps)
  app/routes.py     URLs: pages (HTML) and /api/... (JSON for the JavaScript)
  app/templates/    Jinja2 HTML templates (base.html = header, nav, footer)
  app/static/       CSS, JavaScript, fonts (Barlow, OFL) and D3 (ISC licence)

The browser does the drawing (D3 + plain JavaScript); Python only serves data.
"""

from flask import Flask

from app.data import DEFAULT_RESULTS, AppData


def create_app(results_dir=DEFAULT_RESULTS):
    """Build the app. Tests pass a temporary results folder with tiny fake data."""
    app = Flask(__name__)
    app.config["APP_DATA"] = AppData(results_dir)
    app.json.ensure_ascii = False   # keep "São Paulo" as it is in the JSON

    from app.routes import api, pages
    app.register_blueprint(pages)
    app.register_blueprint(api, url_prefix="/api")
    return app
