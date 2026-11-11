"""The five README screenshots (docs/images/*.png), taken the same way every time.

The images were first taken by hand (2026-10-20). This script makes them reproducible: it starts
the web app on a free local port, opens each page in Microsoft Edge (through Playwright, using the
Edge already installed on Windows, so no browser is downloaded), waits until the fonts and charts
are drawn, and saves the visible part of the window at 1440 x 1000 pixels. It stops with an error
if a page logs a JavaScript error, so a broken page can't end up in the README.

Pages (the framing of the October images, updated for 2026):
  overview.png       the overview, with the 2024 Abu Dhabi pole laps replaying
  lap_compare.png    a 2026 session (Mexico City, the default pair: each driver's fastest lap
                     without a hole in the data)
  corner_lab.png     the default braking zone (2024 Abu Dhabi)
  driver_vs_car.png  scrolled to the H5 section (the 2026 test)
  method.png         the measurement-science page

Everything shown is drawn from the timing data: no logos, photos or broadcast material.
Needs Playwright (tested with 1.64.0: pip install playwright==1.64.0) and the local raw samples
for Lap compare (results/final_2026/raw_samples_2026.parquet). Not part of the tests or CI.
Run from the repo root (~30 s):
    .venv\\Scripts\\python.exe experiments\\31_screenshots.py
"""

import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))      # so `import app` works when this file is run as a script
OUT_DIR = REPO_ROOT / "docs" / "images"
VIEWPORT = {"width": 1440, "height": 1000}
TOPBAR_PX = 64                          # the sticky top bar: a scrolled section starts below it
REPLAY_SECONDS = 5.0                    # how long the overview replay runs before the picture


def start_app():
    """The Flask app on a free port, in a background thread. Returns (server, base URL).

    threaded=True, as `flask run` and app.run use: a single-threaded server serves one
    connection at a time, and a browser keeps connections open, so a page could wait ~20 s
    for a connection the previous page left open (seen on the first run of this script).
    """
    import logging

    from werkzeug.serving import make_server

    from app import create_app

    logging.getLogger("werkzeug").setLevel(logging.ERROR)    # no line per request
    server = make_server("127.0.0.1", 0, create_app(), threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def session_key(base, year, location):
    import json
    import urllib.request

    with urllib.request.urlopen(f"{base}/api/sessions") as response:
        index = json.load(response)
    return next(s["key"] for s in index if s["year"] == year and s["location"] == location)


def shots(base):
    """(file name, path, element to wait for, element to scroll to or None, extra seconds)."""
    mexico = session_key(base, 2026, "Mexico City")
    return [
        ("overview.png", "/", "#hero-svg path", None, REPLAY_SECONDS),     # the drawn track, not the empty svg
        ("lap_compare.png", f"/telemetry?session={mexico}", ".chart-panel", None, 1.0),
        ("corner_lab.png", "/corners", "#tower svg", None, 0.5),
        ("driver_vs_car.png", "/signatures", "#h5-chart svg", "section[aria-labelledby='h5-title']", 0.5),
        ("method.png", "/method", "#funnel-chart svg", None, 0.5),
    ]


def main():
    from playwright.sync_api import sync_playwright

    server, base = start_app()
    errors = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel="msedge")
            for name, path, wait_for, scroll_to, extra in shots(base):
                page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
                page.on("console", lambda m, n=name: errors.append(f"{n}: {m.text}") if m.type == "error" else None)
                page.on("pageerror", lambda e, n=name: errors.append(f"{n}: {e}"))
                page.goto(base + path)
                page.wait_for_selector(wait_for, timeout=30000)
                page.evaluate("document.fonts.ready")
                if scroll_to:
                    top = page.eval_on_selector(scroll_to, "e => e.getBoundingClientRect().top + window.scrollY")
                    page.evaluate(f"window.scrollTo(0, {top - TOPBAR_PX - 16})")
                time.sleep(extra)
                page.screenshot(path=str(OUT_DIR / name))
                print(f"{name:18s} {path}")
                page.close()
            browser.close()
    finally:
        server.shutdown()
    if errors:
        raise SystemExit("JavaScript errors, screenshots not trusted:\n" + "\n".join(errors))


if __name__ == "__main__":
    main()
