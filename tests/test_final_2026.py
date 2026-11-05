"""Tests for the one-time 2026 script (experiments/23_final_2026.py) and h5_protocol.

The guards are the most important part of a one-time test: each reason to stop is checked
on its own, and the real script is started without the switch to see that it stops before
doing anything. Nothing here downloads data.
"""

import importlib.util
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from apextrace import h5_protocol
from apextrace.identification import FEATURE_GROUPS

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "experiments" / "23_final_2026.py"
PART_C = "# Preregistration\n\n## Part C\nThe plan, fully written.\n"


def load_script():
    spec = importlib.util.spec_from_file_location("final_2026", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def problems(tmp_path, **changes):
    """guard_problems with everything in order, except the named changes."""
    arguments = {"switch_value": "1", "preregistration_text": PART_C, "preregistration_committed": "abc123 2026-11-10",
                 "preregistration_unchanged": True, "code_unchanged": True, "code_same_as_part_c": True,
                 "reference_problems": [], "now": datetime(2026, 11, 10, 9, 0), "out_dir": tmp_path / "final_2026"}
    arguments.update(changes)
    return load_script().guard_problems(**arguments)


# ---------------------------------------------------------------- guards

def test_guards_pass_only_when_everything_is_in_order(tmp_path):
    assert problems(tmp_path) == []


def test_each_guard_refuses_on_its_own(tmp_path):
    assert "FINAL_TEST_2026 is not 1" in problems(tmp_path, switch_value=None)[0]
    assert "FINAL_TEST_2026 is not 1" in problems(tmp_path, switch_value="yes")[0]
    assert "not written" in problems(tmp_path, preregistration_text="## Part B only")[0]
    assert "placeholder" in problems(tmp_path, preregistration_text="## Part C\n*To be written*")[0]
    assert "not committed" in problems(tmp_path, preregistration_committed="")[0]
    assert "not committed" in problems(tmp_path, preregistration_unchanged=False)[0]
    assert "uncommitted changes" in problems(tmp_path, code_unchanged=False)[0]
    assert "differs from the commit that added Part C" in problems(tmp_path, code_same_as_part_c=False)[0]
    missing = "results/final/raw_samples_2025.parquet is missing (rebuild it before the run)"
    assert problems(tmp_path, reference_problems=[missing]) == [missing]


def test_the_run_waits_a_day_after_the_fixed_cutoff(tmp_path):
    script = load_script()
    just_too_early = script.CUTOFF_UTC + timedelta(hours=script.CUTOFF_HOURS) - timedelta(minutes=1)
    assert "too early" in problems(tmp_path, now=just_too_early)[0]
    assert problems(tmp_path, now=script.CUTOFF_UTC + timedelta(hours=script.CUTOFF_HOURS)) == []


def test_a_finished_run_can_never_run_again_even_after_renaming(tmp_path):
    renamed = tmp_path / "final_2026_attempt_1"
    renamed.mkdir()
    (renamed / "summary.json").write_text("{}", encoding="utf-8")
    assert "already been run" in problems(tmp_path)[0]
    out_dir = tmp_path / "final_2026"
    out_dir.mkdir()
    (out_dir / "summary.json").write_text("{}", encoding="utf-8")
    assert "already been run" in problems(tmp_path)[0]


def test_an_attempt_that_stopped_early_must_be_recorded_first(tmp_path):
    (tmp_path / "final_2026").mkdir()
    (tmp_path / "final_2026" / "download_log.csv").write_text("round\n", encoding="utf-8")
    message = problems(tmp_path)[0]
    assert "preregistration_deviations.md" in message and "attempt" in message


def test_an_attempt_that_wrote_any_result_counts_as_a_run(tmp_path):
    (tmp_path / "final_2026").mkdir()
    (tmp_path / "final_2026" / "h5_all.csv").write_text("driver\n", encoding="utf-8")
    message = problems(tmp_path)[0]
    assert "counts as a run" in message and "h5_all.csv" in message


def test_the_real_script_stops_without_the_switch_and_creates_nothing():
    environment = {key: value for key, value in os.environ.items() if key != "FINAL_TEST_2026"}
    before = (REPO_ROOT / "results" / "final_2026").exists()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=REPO_ROOT, env=environment,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 1
    assert "STOP" in result.stdout and "FINAL_TEST_2026 is not 1" in result.stdout
    assert (REPO_ROOT / "results" / "final_2026").exists() == before


def test_only_sessions_that_ended_before_the_fixed_cutoff_are_used():
    """The cutoff is a fixed date, so the day of the run can't change which sessions count."""
    script = load_script()
    sessions = pd.DataFrame({"session_key": [1, 2, 3],
                             "date_end": pd.to_datetime(["2026-10-25 15:00", "2026-11-05 23:59", "2026-11-08 15:00"])})
    used = script.sessions_to_use(sessions, datetime(2026, 11, 6, 0, 0))
    assert list(used["session_key"]) == [1, 2]
    assert script.CUTOFF_UTC == datetime(2026, 11, 6, 0, 0)


def test_failed_downloads_are_retried_and_reported(monkeypatch):
    script = load_script()
    calls = {"count": 0}

    def flaky_download(session_key, session_end):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ConnectionError("temporary")
        return {"laps": 10, "kept_laps": 4, "kept_laps_with_data": 4}

    monkeypatch.setattr(script, "download_session", flaky_download)
    sessions = pd.DataFrame({"session_key": [7], "location": ["Somewhere"], "date_end": pd.to_datetime(["2026-03-07"])})
    log = script.download_all(sessions, retries=2, pause_s=0)
    assert log.loc[0, "error"] == "" and log.loc[0, "attempts"] == 2

    def always_failing(session_key, session_end):
        raise ConnectionError("down")

    monkeypatch.setattr(script, "download_session", always_failing)
    log = script.download_all(sessions, retries=2, pause_s=0)
    assert "ConnectionError" in log.loc[0, "error"] and log.loc[0, "attempts"] == 3


# ---------------------------------------------------------------- h5_protocol on synthetic seasons

FEATURES = [feature for group in FEATURE_GROUPS.values() for feature in group]      # the 10 features
COLUMNS = [f"{feature}_rel__slow" for feature in FEATURES]


def seasons_with_a_swap(rng, personal_sd=1.0, teams=4, weekends=12, noise=1.0, car_sd=1.0):
    """Two seasons of lap vectors (car + personal offset + noise, a new car in the target
    season). In the target season the lead drivers of team 0 and team 1 swap teams."""
    rows = []
    personal = {}
    for team in range(teams):
        for name in (f"A{team}", f"B{team}"):
            personal[name] = rng.normal(0, personal_sd, len(COLUMNS))
    lineup = {2025: {team: [f"A{team}", f"B{team}"] for team in range(teams)}}
    lineup[2026] = {team: list(drivers) for team, drivers in lineup[2025].items()}
    lineup[2026][0][0], lineup[2026][1][0] = "A1", "A0"
    names = ["Ferrari", "Mercedes", "McLaren", "Williams"]
    for year in (2025, 2026):
        for team, drivers in lineup[year].items():
            car = rng.normal(0, car_sd, len(COLUMNS))
            for weekend in range(weekends):
                for name in drivers:
                    for lap in range(2):
                        values = car + personal[name] + rng.normal(0, noise, len(COLUMNS))
                        rows.append({"year": year, "session_key": year * 100 + weekend, "driver": name,
                                     "team": names[team], "lap": lap, **dict(zip(COLUMNS, values))})
    return pd.DataFrame(rows)


def test_feature_sets_have_the_planned_sizes():
    columns = [f"{feature}_rel__{corner}" for feature in FEATURES for corner in ("slow", "medium", "fast")]
    sizes = {name: len(chosen) for name, chosen in h5_protocol.feature_sets(columns).items()}
    assert sizes == {"all": 30, "control points": 12, "energy-sensitive": 12, "no throttle": 24}


def test_h5_results_find_a_personal_signature_and_say_supported():
    laps = seasons_with_a_swap(np.random.default_rng(21))
    _, summary = h5_protocol.h5_results(laps, 2025, 2026)
    primary = summary["sets"]["all"]
    assert primary["drivers"] == 8 and primary["own_closer"] >= 7
    assert summary["supported"]


def test_h4_results_find_the_swapped_drivers_from_the_team_names():
    laps = seasons_with_a_swap(np.random.default_rng(22))
    changes, changers, stayers, summary = h5_protocol.h4_results(laps, 2025, 2026)
    assert summary["changer_names"] == ["A0", "A1"]
    assert set(changers.loc[changers["included"], "teammate_target"]) == {"B0", "B1"}
    assert summary["stayers"]["drivers"] == 6
    assert summary["changers"]["test_possible"] is False      # 2 changers: descriptive only
    assert "not a decision" in summary["note"]


def test_sign_summary_survives_a_group_where_nobody_could_be_compared():
    table = pd.DataFrame([{"driver": "X", "included": False, "reason": "fewer than 5 weekends"}])
    summary = h5_protocol.sign_summary(table)
    assert summary["drivers"] == 0 and summary["sign_test_p"] is None and summary["test_possible"] is False


def test_h5_is_not_testable_when_no_2026_driver_has_enough_weekends():
    laps = seasons_with_a_swap(np.random.default_rng(23))
    laps = laps[(laps["year"] == 2025) | (laps["session_key"] < 2026 * 100 + 3)]     # 3 weekends in 2026
    _, summary = h5_protocol.h5_results(laps, 2025, 2026)
    assert summary["sets"]["all"]["drivers"] == 0
    assert summary["verdict"] == "not testable" and summary["supported"] is False


def test_corner_type_counts_per_season():
    corners = pd.DataFrame({"session_key": [1, 1, 1, 2], "type": ["slow", "medium", "slow", "fast"]})
    counts = h5_protocol.corner_type_counts(corners)
    assert counts["slow"] == {"corners": 2, "per_session": 1.0}
    assert counts["fast"]["corners"] == 1 and counts["medium"]["per_session"] == 0.5
