"""build_session (one qualifying session -> dataset rows) run end to end on synthetic laps.

This is the code that built every dataset in the project (development, 2025 and 2026), but until
2026-11-18 no test ran it: only the experiments did, on real data, where the right answer is
unknown. Here the four OpenF1 functions that need the network are replaced by stand-ins that
serve synthetic laps; everything else is the real code: lap selection, the reference lap, corner
detection, the usable-window rule (no gap over 0.6 s), the fused coordinate and the features.

Each synthetic lap is two corners from synthetic.make_true_corner (a heavy-braking one, then a
medium one) joined end to end, sampled like the live feed (0.24-0.32 s apart, whole km/h and %,
brake on/off) with 1-2 m of position noise. Because the laps are synthetic, the true brake onset
of every corner pass is known, and the measured one is compared with it.
"""

import numpy as np
import pandas as pd
import pytest

from apextrace import session_build, synthetic

SESSION = {"session_key": 9999, "date_end": "2024-01-01T13:00:00+00:00", "location": "Testville"}
FIRST_LAP_START = pd.Timestamp("2024-01-01 12:00:00", tz="UTC")
INTERVALS_S = [0.24, 0.28, 0.32]          # within the feed's 0.16-0.56 s, no gap over 0.6 s


def synthetic_truth(rng):
    """Two corners joined end to end: heavy braking, then medium. Returns (truth, true onsets in m)."""
    parts = []
    for kind in ("heavy_braking", "medium"):
        params = synthetic.random_corner_params(kind, rng)
        params["straight_s"] = 3.0        # the same straight every lap, so lap times stay within 107 %
        parts.append(synthetic.make_true_corner(params))
    columns = {"time_s": [], "distance_m": [], "speed_kmh": [], "throttle_pct": [], "brake": []}
    onsets = []
    time_shift, distance_shift = 0.0, 0.0
    for part in parts:
        columns["time_s"].append(part["time_s"] + time_shift)
        columns["distance_m"].append(part["distance_m"] + distance_shift)
        for name in ("speed_kmh", "throttle_pct", "brake"):
            columns[name].append(part[name])
        onsets.append(part["events"]["brake_onset"]["d"] + distance_shift)
        time_shift = columns["time_s"][-1][-1] + 0.002
        distance_shift = columns["distance_m"][-1][-1]
    truth = {name: np.concatenate(values) for name, values in columns.items()}
    return truth, onsets


def feed_samples(truth, rng, gap_at_s=None):
    """The lap as lap_samples_on_track would return it: car samples on the track coordinate,
    integrated distance, and position samples. gap_at_s removes the car samples within 0.7 s
    of that time (a 1.4 s feed gap).

    Integrated distance is given a per-lap offset of 20-40 m (either sign) from the track
    coordinate, as real laps have offsets of several metres: only the fused coordinate removes
    it, so a measurement taken on integrated distance alone would be off by that much."""
    feed = synthetic.degrade_like_feed(truth, INTERVALS_S, [1 / 3, 1 / 3, 1 / 3], rng)
    if gap_at_s is not None:
        keep = np.abs(feed["time_s"] - gap_at_s) > 0.7
        feed = {name: values[keep] for name, values in feed.items()}
    times = feed["time_s"]
    true_s = np.interp(times, truth["time_s"], truth["distance_m"])
    speed_ms = feed["speed_kmh"] / 3.6
    integrated = np.concatenate([[0.0], np.cumsum(np.diff(times) * (speed_ms[1:] + speed_ms[:-1]) / 2)])
    integrated = integrated + true_s[0] + rng.choice([-1.0, 1.0]) * rng.uniform(20.0, 40.0)
    pos_times = np.arange(rng.uniform(0.0, 0.27), truth["time_s"][-1], 0.27)
    pos_s = np.interp(pos_times, truth["time_s"], truth["distance_m"]) + rng.normal(0.0, 2.0, len(pos_times))
    return {
        "time_s": times, "s_m": true_s + rng.normal(0.0, 1.0, len(times)), "d_m": integrated,
        "speed_kmh": feed["speed_kmh"], "throttle_pct": feed["throttle_pct"], "brake": feed["brake"],
        "gear": np.full(len(times), 5),
        "pos_time_s": pos_times, "pos_s_m": pos_s, "pos_d_m": np.interp(pos_times, times, integrated),
        "pos_x_m": pos_s, "pos_y_m": np.zeros(len(pos_times)),
    }


def lap_row(driver, number, lap_number, start, seconds):
    return {"Driver": driver, "DriverNumber": str(number), "Team": "Test Team", "LapNumber": lap_number,
            "Stint": 1, "Compound": "SOFT", "TyreLife": lap_number, "LapStartDate": start,
            "LapTime": pd.Timedelta(seconds, unit="s"), "PitOutTime": pd.NaT, "PitInTime": pd.NaT,
            "Deleted": False, "DeletedReason": "", "TrackStatus": "1", "IsAccurate": True}


@pytest.fixture(scope="module")
def built():
    return build_synthetic_session()


def build_synthetic_session():
    """Three drivers x three laps. AAA's second lap has a feed gap in the second corner; CCC has
    the fastest laps but no car data, so the reference must come from another driver."""
    rng = np.random.default_rng(2026)
    laps, samples, truth_onsets = [], {}, {}
    start = FIRST_LAP_START
    for driver, number in (("AAA", 1), ("BBB", 2)):
        for lap_number in (1, 2, 3):
            truth, onsets = synthetic_truth(rng)
            gap = None
            if driver == "AAA" and lap_number == 2:
                gap = float(np.interp(onsets[1], truth["distance_m"], truth["time_s"]))
            samples[(number, start)] = feed_samples(truth, rng, gap_at_s=gap)
            truth_onsets[(driver, lap_number)] = onsets
            laps.append(lap_row(driver, number, lap_number, start, truth["time_s"][-1]))
            start = start + pd.Timedelta(120, unit="s")
    for lap_number in (1, 2, 3):
        laps.append(lap_row("CCC", 3, lap_number, start, 15.0))     # fastest, but no car data
        start = start + pd.Timedelta(120, unit="s")
    lap_table = pd.DataFrame(laps)
    for column in ("PitOutTime", "PitInTime"):                        # as FastF1/OpenF1 give them
        lap_table[column] = pd.Series(pd.NaT, index=lap_table.index, dtype="timedelta64[ns]")
    lap_length = float(max(s["s_m"][-1] for s in samples.values()))

    stand_ins = {
        "lap_table": lambda key, date_end: lap_table.copy(),
        "driver_streams": lambda key, number, span_start, span_end: None if number == 3 else {"number": number},
        "reference_from_lap": lambda key, number, lap_start, lap_time, streams: {"length": lap_length},
        "lap_samples_on_track": lambda key, number, lap_start, lap_time, reference, streams: samples[(number, lap_start)],
    }
    with pytest.MonkeyPatch.context() as patch:
        for name, function in stand_ins.items():
            patch.setattr(session_build, name, function)
        rows, corner_rows, summary, raw = session_build.build_session(2024, 1, SESSION)
    return pd.DataFrame(rows), corner_rows, summary, raw, truth_onsets, samples


def test_session_summary_counts(built):
    rows, corner_rows, summary, raw, _, _ = built
    assert summary["laps"] == 9 and summary["kept_laps"] == 9
    assert summary["corners"] == 2 == len(corner_rows)                # the two synthetic corners, nothing else
    assert summary["pairs"] == 9 * 2 == len(rows)
    assert summary["reference"].startswith("AAA") or summary["reference"].startswith("BBB")   # not CCC


def test_unusable_rows_have_their_reason(built):
    rows, _, summary, _, _, _ = built
    no_data = rows[rows["driver"] == "CCC"]
    assert len(no_data) == 6 and set(no_data["reason"]) == {"no car/position data"}
    gap = rows[rows["reason"] == "feed gap in window"]
    assert list(zip(gap["driver"], gap["lap"])) == [("AAA", 2)]
    assert gap["corner_s_m"].iloc[0] == rows["corner_s_m"].max()     # the second corner, not the first
    assert summary["usable_pairs"] == 18 - 6 - 1 == int(rows["usable"].sum())


def test_measured_brake_onset_matches_the_truth(built):
    """The whole path: window -> fused coordinate -> brake onset, against the true onset in metres."""
    rows, _, _, _, truth_onsets, _ = built
    usable = rows[rows["usable"]].sort_values(["driver", "lap", "corner_s_m"])
    errors = []
    for (driver, lap), lap_rows in usable.groupby(["driver", "lap"]):
        corner_order = sorted(rows.loc[(rows["driver"] == driver) & (rows["lap"] == lap), "corner_s_m"])
        for _, row in lap_rows.iterrows():
            true_onset = truth_onsets[(driver, lap)][corner_order.index(row["corner_s_m"])]
            errors.append(row["corner_s_m"] + row["brake_onset_m"] - true_onset)
    errors = np.array(errors)
    assert len(errors) == 11
    assert np.all(np.abs(errors) < 15.0), errors          # chosen estimator: ~4 m RMS, plus the coordinate
    assert np.sqrt(np.mean(errors ** 2)) < 8.0, errors


def test_raw_sample_table_keeps_every_measured_sample(built):
    _, _, _, raw, _, samples = built
    expected = sum(len(s["time_s"]) for s in samples.values())        # AAA and BBB, three laps each
    assert len(raw) == expected
    assert set(raw["driver"]) == {"AAA", "BBB"}
    assert raw["gear"].dtype.kind == "i"
    first = samples[(1, FIRST_LAP_START)]
    lap = raw[(raw["driver"] == "AAA") & (raw["lap"] == 1)]
    assert np.allclose(lap["time_s"], np.round(first["time_s"], 3))
    assert np.allclose(lap["x_m"], np.round(np.interp(first["time_s"], first["pos_time_s"], first["pos_x_m"]), 2))
