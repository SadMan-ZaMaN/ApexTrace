"""Web app (Phase 8): the lap-comparison helpers and the JSON API, on synthetic laps only.

Synthetic setup: a circular 2,000 m track, laps sampled ~3.8 times a second
with irregular gaps (like the real feed), so the expected gap between two laps
is known exactly.
"""

import json

import numpy as np
import pandas as pd
import pytest

from app import create_app
from app.data import delta_time, fused_distance, increasing_distance, mini_sectors

TRACK_M = 2000.0
RADIUS = TRACK_M / (2 * np.pi)


def lap_samples(speeds, rng, position_offset_m=0.0, position_noise_m=0.0, drift=0.0):
    """Sample a lap whose speed (m/s) is given per metre of track.

    Returns time, true distance, projected position s (with an offset and noise,
    like X/Y projection), integrated distance d (with a scale drift, like a
    wheel-speed integral) and speed.
    """
    metres = np.arange(len(speeds) + 1, dtype=float)
    time_at_metre = np.concatenate([[0.0], np.cumsum(1.0 / np.asarray(speeds))])   # dt = ds / v
    lap_time = time_at_metre[-1]
    times = [0.04]
    while True:
        step = rng.choice([0.16, 0.2, 0.24, 0.28, 0.32])     # irregular gaps on a 40 ms clock
        if times[-1] + step >= lap_time:
            break
        times.append(times[-1] + step)
    times = np.array(times)
    true_s = np.interp(times, time_at_metre, metres)
    speed = np.interp(true_s, metres[:-1], speeds)
    s = true_s + position_offset_m + rng.normal(0, position_noise_m, len(times)) if position_noise_m else true_s + position_offset_m
    d = true_s * (1 + drift)
    return {"t": times, "true_s": true_s, "s": s, "d": d, "speed": speed, "lap_time": lap_time}


def two_laps(rng, noise=True):
    """A at 60 m/s everywhere; B the same except 50 m/s from 800 m to 1,100 m.

    Expected gap: 0 before 800 m, 300/50 - 300/60 = 1.0 s from 1,100 m on.
    """
    speed_a = np.full(int(TRACK_M), 60.0)
    speed_b = speed_a.copy()
    speed_b[800:1100] = 50.0
    a = lap_samples(speed_a, rng, position_offset_m=0.0, position_noise_m=3.0 if noise else 0.0, drift=0.0025)
    b = lap_samples(speed_b, rng, position_offset_m=5.0, position_noise_m=3.0 if noise else 0.0, drift=0.0025)
    return a, b


# ---------------------------------------------------------------- pure helpers

def test_increasing_distance_drops_samples_that_step_backwards():
    s, t = increasing_distance([10.0, 22.5, 22.3, 35.1], [0.0, 0.2, 0.4, 0.6])
    assert list(s) == [10.0, 22.5, 35.1]
    assert list(t) == [0.0, 0.2, 0.6]


def test_delta_time_recovers_a_known_gap_on_clean_samples():
    a, b = two_laps(np.random.default_rng(1), noise=False)
    grid, delta = delta_time(a["d"], a["t"], b["d"], b["t"])
    assert np.max(np.abs(delta[grid < 790])) < 0.01                  # level before the slow stretch
    assert delta[grid > 1110] == pytest.approx(np.ones(np.sum(grid > 1110)), abs=0.01)   # 1.0 s after it


def test_gap_from_integrated_distance_beats_projected_position():
    # Full path at realistic noise: projected position has a lap-specific 5 m
    # offset and 3 m scatter; integrated distance is smooth and drifts the same
    # way on both laps. The gap must come out right only with d (the fix of 2026-10-19).
    a, b = two_laps(np.random.default_rng(2))
    grid_d, delta_d = delta_time(a["d"], a["t"], b["d"], b["t"])
    grid_s, delta_s = delta_time(a["s"], a["t"], b["s"], b["t"])
    after_d = delta_d[(grid_d > 1200) & (grid_d < 1900)]
    after_s = delta_s[(grid_s > 1200) & (grid_s < 1900)]
    # (jitter = step-to-step change on the flat stretch, where the true gap is constant)
    assert np.mean(np.abs(after_d - 1.0)) < 0.02
    assert np.std(np.diff(after_d)) < 0.005                          # smooth
    assert np.mean(np.abs(after_s - 1.0)) > 0.05                     # the offset biases it ...
    assert np.std(np.diff(after_s)) > 0.02                           # ... and the scatter shakes it


def test_fused_distance_removes_scatter_and_drift():
    rng = np.random.default_rng(3)
    a = lap_samples(np.full(int(TRACK_M), 60.0), rng, position_noise_m=3.0, drift=0.006)
    fused = fused_distance(a["s"], a["d"], window_m=400)
    error = fused - a["true_s"]
    middle = (a["true_s"] > 300) & (a["true_s"] < 1700)               # away from the lap ends
    assert np.sqrt(np.mean(error[middle] ** 2)) < 1.5                  # vs 3 m scatter in s
    assert np.abs(a["d"][-1] - a["true_s"][-1]) > 10                   # d alone drifted > 10 m
    assert np.abs(error[middle]).max() < 4.0


def test_mini_sectors_name_the_faster_driver_and_call_small_gains_even():
    grid = np.arange(0, 3000, 5.0)
    delta = np.where(grid < 1000, 0.0, np.where(grid < 2000, (grid - 1000) / 1000 * 0.3, 0.3 - (grid - 2000) / 1000 * 0.1))
    sectors = mini_sectors(grid, delta, count=3)
    assert [s["faster"] for s in sectors] == ["even", "a", "b"]       # flat, B loses 0.3 s, B gains 0.1 s
    assert sectors[1]["gain_s"] == pytest.approx(0.3, abs=0.01)
    tiny = mini_sectors(grid, grid * 1e-5, count=3)                     # 0.01 s per sector: inside the error
    assert all(s["faster"] == "even" for s in tiny)


# ---------------------------------------------------------------- the Flask app on a fake results folder

def fake_results(root, rng, with_raw=True):
    """A results/ folder with one session, two drivers, one lap each (synthetic)."""
    app_dir = root / "app"
    app_dir.mkdir(parents=True)
    angles = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    track = {"centre": [0.0, 0.0], "rotation_deg": 0.0, "length_m": TRACK_M,
             "s": list(angles / (2 * np.pi) * TRACK_M), "x": list(RADIUS * np.cos(angles)), "y": list(RADIUS * np.sin(angles))}
    a, b = two_laps(rng)
    drivers = []
    rows = []
    for code, team, colour, lap in [("AAA", "Team One", "#ff8000", a), ("BBB", "Team One", "#ff8000", b)]:
        drivers.append({"code": code, "number": 1, "name": code, "team": team, "colour": colour,
                        "laps": [{"lap": 5, "time_s": round(lap["lap_time"], 3), "compound": "SOFT", "tyre_life": 2,
                                  "samples": len(lap["t"])}]})
        for i in range(len(lap["t"])):
            angle = lap["true_s"][i] / RADIUS
            rows.append({"year": 2024, "session_key": 1, "driver": code, "lap": 5, "time_s": lap["t"][i],
                         "s_m": lap["s"][i], "d_m": lap["d"][i], "speed_kmh": round(lap["speed"][i] * 3.6),
                         "throttle_pct": 100.0, "brake": False, "gear": 7,
                         "x_m": RADIUS * np.cos(angle), "y_m": RADIUS * np.sin(angle)})
    session = {"key": 1, "year": 2024, "round": 1, "location": "Testville", "country": "Nowhere", "circuit": "Ring",
               "date": "2024-01-01", "note": "", "wet": False, "track": track, "drivers": drivers,
               "corners": [{"name": "C1", "s_m": 950.0, "type": "medium", "min_speed_kmh": 180, "entry_speed_kmh": 216}]}
    hero = {"session_key": 1, "year": 2024, "location": "Testville", "country": "Nowhere", "circuit": "Ring",
            "track": track, "corners": session["corners"], "cars": [
                {"code": d["code"], "team": d["team"], "colour": d["colour"], "lap": 5, "lap_time_s": d["laps"][0]["time_s"],
                 "t": [0.0, 1.0], "s": [0.0, 60.0], "x": [0.0, 1.0], "y": [0.0, 1.0], "speed": [216, 216]}
                for d in drivers]}
    headline = {"data": {"sample_rate_hz": 3.77, "sessions": 1, "sessions_built": 1, "raw_samples": len(rows),
                         "clean_corner_passes": 2, "features": 11, "drivers": 2, "alignment_error_m": 1.15},
                "hypotheses": [{"id": "H1", "question": "Q?", "result": "r", "detail": "d", "verdict": "partly",
                                "data": "2024", "source": "x"}],
                "preregistration": {"part_a": "aaaaaaa", "part_b": "bbbbbbb"}}
    for name, content in [("sessions.json", [session]), ("hero.json", hero), ("headline.json", headline)]:
        (app_dir / name).write_text(json.dumps(content), encoding="utf-8")
    if with_raw:
        (root / "09_dataset").mkdir()
        pd.DataFrame(rows).to_parquet(root / "09_dataset" / "raw_samples.parquet", index=False)
    return a, b


@pytest.fixture
def client(tmp_path):
    fake_results(tmp_path, np.random.default_rng(4))
    return create_app(tmp_path).test_client()


def test_pages_render(client):
    for path in ["/", "/telemetry"]:
        response = client.get(path)
        assert response.status_code == 200
        assert b"not associated" in response.data            # the unofficial-project notice is on every page


def test_compare_returns_both_laps_and_a_correct_gap(client):
    response = client.get("/api/compare/1?a=AAA:5&b=BBB:5")
    assert response.status_code == 200
    body = response.get_json()
    assert set(body) == {"a", "b", "delta", "mini_sectors"}
    s, gap = np.array(body["delta"]["s"]), np.array(body["delta"]["d"])
    assert np.mean(np.abs(gap[(s > 1200) & (s < 1900)] - 1.0)) < 0.02   # the 1.0 s B lost at 800-1,100 m
    faster = [m["faster"] for m in body["mini_sectors"]]
    assert "a" in faster and "b" not in faster                           # only A was ever faster


def test_api_rejects_bad_input(client):
    assert client.get("/api/compare/1?a=aaa:5&b=BBB:5").status_code == 400      # not a driver code
    assert client.get("/api/compare/1?a=AAA:x&b=BBB:5").status_code == 400      # not a lap number
    assert client.get("/api/compare/99?a=AAA:5&b=BBB:5").status_code == 404     # unknown session
    assert client.get("/api/compare/1?a=AAA:9&b=BBB:5").status_code == 404      # no such lap


def test_corner_lab_feature_list_is_the_research_feature_list():
    from apextrace.identification import ALL_FEATURES
    from app.data import CORNER_FEATURES
    assert CORNER_FEATURES == ALL_FEATURES      # the app's copy must not drift from the analysis


def fake_dataset_row(lap, compound="SOFT", brake_onset=-110.0):
    row = {"session_key": 1, "driver": "AAA", "team": "Team One", "lap": lap, "lap_time_s": 90.0 + lap,
           "corner": "C1", "corner_type": "medium", "usable": True, "compound": compound}
    values = {"brake_onset_m": brake_onset, "braking_distance_m": 95.0, "mean_decel_ms2": 30.0, "min_speed_kmh": 172.0,
              "apex_m": -12.0, "throttle_pickup_m": 5.0, "full_throttle_m": 60.0, "entry_speed_kmh": 290.0,
              "exit_speed_kmh": 210.0, "corner_time_s": 5.1, "min_gear": 4}
    return {**row, **values}


def test_corner_rows_use_the_research_cleaning_rules(tmp_path):
    fake_results(tmp_path, np.random.default_rng(6))
    rows = [fake_dataset_row(1), fake_dataset_row(2, compound="WET"), fake_dataset_row(3, brake_onset=21.0)]
    pd.DataFrame(rows).to_csv(tmp_path / "09_dataset" / "dataset.csv.gz", index=False)
    client = create_app(tmp_path).test_client()
    body = client.get("/api/corners/1").get_json()
    laps = {r["lap"]: r for r in body["rows"]}
    assert set(laps) == {1, 3}                                  # the wet lap is not analysed
    assert laps[1]["brake_onset_m"] == -110.0
    assert laps[3]["brake_onset_m"] is None                     # braking after the marker: impossible -> missing
    assert laps[3]["braking_distance_m"] is None                # ... and what is computed from it
    assert laps[3]["min_speed_kmh"] == 172.0                    # the rest of the row is kept


def test_optional_exports_are_served_or_explained(tmp_path):
    fake_results(tmp_path, np.random.default_rng(7))
    client = create_app(tmp_path).test_client()
    for endpoint in ["/api/features", "/api/identification", "/api/signatures", "/api/method"]:
        response = client.get(endpoint)
        assert response.status_code == 503
        assert "16_app_data" in response.get_json()["hint"]
    (tmp_path / "app" / "features.json").write_text(json.dumps({"features": []}), encoding="utf-8")
    assert create_app(tmp_path).test_client().get("/api/features").status_code == 200
    for page in ["/corners", "/signatures", "/method"]:
        assert client.get(page).status_code == 200


def test_missing_raw_samples_give_a_clear_503(tmp_path):
    fake_results(tmp_path, np.random.default_rng(5), with_raw=False)
    client = create_app(tmp_path).test_client()
    assert client.get("/api/sessions/1").get_json()["raw_available"] is False
    response = client.get("/api/compare/1?a=AAA:5&b=BBB:5")
    assert response.status_code == 503
    assert "09_build_dataset" in response.get_json()["hint"]
