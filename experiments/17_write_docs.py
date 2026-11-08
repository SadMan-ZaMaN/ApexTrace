"""Phase 8: write README.md and docs/report.md from templates, with every number taken from results files.

Project rule: numbers in the README and the report come only from experiment
scripts, never typed by hand. So the two documents are templates
(docs/templates/*.j2) with placeholders like {{ h3.final.ours }}, and this
script fills them from the results/ summaries, like a mail merge.

  - collect_numbers() reads the result files and formats every number once;
  - the Jinja2 template engine (the same one Flask uses for the web pages)
    replaces the placeholders; StrictUndefined makes a placeholder with no
    matching number an ERROR, so a typo can't silently print nothing.

To change the wording: edit docs/templates/*.j2, then run this script.
Never edit README.md or docs/report.md directly (they say so at the top).

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\17_write_docs.py
"""

import json
from datetime import timedelta
from pathlib import Path

import pandas as pd
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from apextrace.dataset import clean, load_dataset

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
TEMPLATES = REPO_ROOT / "docs" / "templates"
OUTPUTS = {"README.md.j2": REPO_ROOT / "README.md", "report.md.j2": REPO_ROOT / "docs" / "report.md"}


def load(relative):
    with open(RESULTS / relative, encoding="utf-8") as file:
        return json.load(file)


# ---------------------------------------------------------------- formatting

def p_value(p):
    """0.0273 -> '0.027', 0.00129 -> '0.0013', 0.000105 -> '< 0.001' (two significant digits)."""
    if p < 0.001:
        return "< 0.001"
    return f"{p:.2g}"


def p_text(p):
    """'p = 0.027' or 'p < 0.001'."""
    text = p_value(p)
    return f"p {text}" if text.startswith("<") else f"p = {text}"


def f(value, digits):
    """A number with a fixed number of decimals, and a real minus sign."""
    return f"{value:.{digits}f}".replace("-", "−")


def thousands(value):
    return f"{int(value):,}"


def interval(block, digits=3):
    return f"[{block['ci95_low']:.{digits}f}, {block['ci95_high']:.{digits}f}]"


# ---------------------------------------------------------------- the numbers

def collect_numbers():
    n = {}

    # --- the data
    timing = load("01_data_pilot/summary.json")["check_1_sample_timing"]["car"]
    n["data"] = {
        "rate_hz": f(timing["rate_from_mean_hz"], 2), "nyquist_hz": f(timing["rate_from_mean_hz"] / 2, 2),
        "interval_median_s": f(timing["median_s"], 2), "interval_p5_s": f(timing["p5_s"], 2),
        "interval_p95_s": f(timing["p95_s"], 2), "interval_max_s": f(timing["max_s"], 2),
        "clock_ms": f(timing["clock_tick_s"] * 1000, 0),
        "metres_between_samples_300": f(timing["metres_between_samples"]["300 km/h"]["mean"], 0),
    }
    dataset = load("09_dataset/summary.json")
    repeat = load("11_repeatability/summary.json")
    final = load("final/summary.json")
    dev_clean, _ = clean(load_dataset())
    final_clean, _ = clean(pd.read_csv(RESULTS / "final" / "dataset_2025.csv.gz"))
    sessions_2025 = pd.read_csv(RESULTS / "final" / "sessions_2025.csv")
    download_log = pd.read_csv(RESULTS / "08_download" / "download_log.csv")
    headline = load("app/headline.json")["data"]
    n["data"].update({
        "sessions_dev": dataset["sessions"], "sessions_dev_with_data": dataset["sessions_with_data"],
        "sessions_dev_clean": int(dev_clean["session_key"].nunique()),
        "sessions_2025": int(len(sessions_2025)), "sessions_2025_built": int((sessions_2025["laps"] > 0).sum()),
        "sessions_2025_clean": int(final_clean["session_key"].nunique()),
        "sessions_clean_total": int(dev_clean["session_key"].nunique() + final_clean["session_key"].nunique()),
        "rows_dev": thousands(dataset["rows"]), "usable_dev": thousands(dataset["usable_rows"]),
        "clean_dev": thousands(repeat["cleaning"]["clean_rows"]),
        "usable_2025": thousands(final["cleaning_2025"]["usable_rows"]),
        "clean_2025": thousands(final["cleaning_2025"]["clean_rows"]),
        "clean_total": thousands(repeat["cleaning"]["clean_rows"] + final["cleaning_2025"]["clean_rows"]),
        "drivers_dev": dataset["drivers"], "corners_dev": dataset["corners"], "features": len(dataset["features"]),
        "laps_dev": thousands(dataset["laps"]), "raw_samples_millions": f(headline["raw_samples"] / 1e6, 2),
        # kept by the lap-selection rules (the download log); laps_dev = those that reached the dataset
        "laps_dev_kept": thousands(download_log["kept_laps"].sum()),
        "drivers_total": headline["drivers"],
        # the logged 2023-2024 download: OpenF1's rate limit sets the pace
        "download_minutes": f(download_log["seconds"].sum() / 60, 0),
        "download_per_session_s": f(download_log["seconds"].median(), 0),
    })

    # --- OpenF1 = the same feed as FastF1 (validation on 2024 Abu Dhabi)
    validation = load("07_openf1_validation/summary.json")
    n["validation"] = {
        "q_laps": validation["lap_tables"]["Q"]["laps_in_both"],
        "kept_same_q": validation["kept_laps"]["Q"]["same_kept_laps"], "kept_drivers": validation["kept_laps"]["Q"]["drivers"],
        "kept_same_fp2": validation["kept_laps"]["FP2"]["same_kept_laps"],
        "brake_onset_max_diff_m": f(validation["features"]["brake_onset_m"]["max_abs_diff"], 2),
    }

    # --- measurement science (Phase 2)
    shift = load("02_group_delay/summary.json")["A_braking_shift_heavy_braking"]
    errors = pd.DataFrame(load("03_synthetic_errors/summary.json")["rows"])
    real = errors[(errors["scenario"] == "real") & (errors["corner_type"] == "heavy_braking")].set_index(["feature", "estimator"])
    peak = real.loc["peak_decel_ms2"]["rmse"]
    n["measure"] = {
        "mc_laps": thousands(load("03_synthetic_errors/summary.json")["laps_per_type"]),
        "ma5_mid_shift_m": f(shift["moving average 5, causal"]["mid_mean_shift_m"], 1),
        "butter_mid_shift_m": f(shift["Butterworth 0.5 Hz, causal"]["mid_mean_shift_m"], 1),
        "zero_phase_mid_shift_m": f(shift["moving average 5, zero-phase"]["mid_mean_shift_m"], 1),
        "zero_phase_onset_shift_m": f(shift["moving average 5, zero-phase"]["onset_mean_shift_m"], 1),
        "onset_naive_bias_m": f(real.loc[("brake_onset_m", "first on sample"), "bias"], 1),
        "onset_naive_rmse_m": f(real.loc[("brake_onset_m", "first on sample"), "rmse"], 1),
        "onset_chosen_rmse_m": f(real.loc[("brake_onset_m", "speed breakpoint inside off-on interval"), "rmse"], 1),
        "apex_lowest_rmse_m": f(real.loc[("apex_m", "lowest sample"), "rmse"], 1),
        "apex_parabola_rmse_m": f(real.loc[("apex_m", "parabola 3 points"), "rmse"], 1),
        "min_speed_rmse_kmh": f(real.loc[("min_speed_kmh", "parabola 3 points"), "rmse"], 2),
        "pickup_first_rmse_m": f(real.loc[("throttle_pickup_m", "first sample >= 10 %"), "rmse"], 1),
        "pickup_interp_rmse_m": f(real.loc[("throttle_pickup_m", "interpolated crossing"), "rmse"], 1),
        "peak_decel_best_rmse": f(peak.min(), 1),
        "alignment_m": f(load("04_alignment/summary.json")["fusion_offset_noise_m"], 2),
    }

    # --- pilot (H2)
    pilot = load("06_pilot_stats/summary.json")
    onset = {r["corner"]: r for r in pilot["h2"] if r["feature"] == "brake_onset_m"}
    n["pilot"] = {
        "tests": len(pilot["h2"]), "discoveries": pilot["discoveries"], "commit": pilot["preregistration_commit"][:7],
        "laps_nor": onset["T5"]["n_NOR"], "laps_pia": onset["T5"]["n_PIA"],
        "t5_diff_m": f(onset["T5"]["difference_NOR_minus_PIA"], 1), "t5_g": f(onset["T5"]["hedges_g"], 1),
        "t5_p": p_value(onset["T5"]["p_permutation"]),
        "t9_diff_m": f(onset["T9"]["difference_NOR_minus_PIA"], 1), "t9_g": f(onset["T9"]["hedges_g"], 1),
        "t9_p": p_value(onset["T9"]["p_permutation"]),
    }

    # --- H1 repeatability
    rows = pd.DataFrame(repeat["rows"])
    ratio = rows["sd_over_measurement_error"].dropna()
    weekend = rows.sort_values("icc_weekend")
    n["h1"] = {
        "lap_min": f(rows["icc_lap"].min(), 2), "lap_max": f(rows["icc_lap"].max(), 2),
        "weekend_min": f(rows["icc_weekend"].min(), 2), "weekend_max": f(rows["icc_weekend"].max(), 2),
        "ratio_min": f(ratio.min(), 1), "ratio_max": f(ratio.max(), 0), "ratio_cases": int(len(ratio)),
        "brake_slow_lap": f(rows.set_index(["corner_type", "feature"]).loc[("slow", "brake_onset_m"), "icc_lap"], 2),
        "brake_slow_weekend": f(rows.set_index(["corner_type", "feature"]).loc[("slow", "brake_onset_m"), "icc_weekend"], 2),
        "best_weekend": [f"{r.feature} ({r.corner_type}, {r.icc_weekend:.2f})" for r in weekend.tail(3)[::-1].itertuples()],
    }

    # --- H3 identification
    def h3_block(block):
        out = {}
        for key, name in [("ours", "our features | balanced_accuracy"), ("lap_time", "lap time only | balanced_accuracy"),
                          ("raw", "raw lap statistics | balanced_accuracy"), ("vote", "our features | weekend vote"),
                          ("shuffled", "shuffled labels | balanced_accuracy"),
                          ("no_throttle", "without throttle | balanced_accuracy")]:
            out[key] = f(block[name]["mean"], 3)
            out[key + "_ci"] = interval(block[name])
        lt, raw = block["ours minus lap time only"], block["ours minus raw lap statistics"]
        out.update({"wins": lt["wins"], "teams": lt["team_seasons"], "p": p_text(lt["wilcoxon_p"]),
                    "raw_wins": raw["wins"], "raw_p": p_text(raw["wilcoxon_p"])})
        return out

    dev_id = load("12_identification/summary.json")
    seasons = {s["year"]: s for s in dev_id["seasons"]}
    n["h3"] = {"dev": h3_block(dev_id["teammates"]), "final": h3_block(final["h3"]), "laps_dev": thousands(dev_id["laps"]),
               "laps_2025": thousands(final["laps_2025"]),
               "multi": {str(y): {"drivers": s["drivers"], "ours": f(s["our features | balanced_accuracy"], 3),
                                  "raw": f(s["raw lap statistics | balanced_accuracy"], 3),
                                  "lap_time": f(s["lap time only | balanced_accuracy"], 3),
                                  "chance": f(s["chance"], 3)} for y, s in seasons.items()},
               "supported": final["h3_supported"]}
    teams_2025 = pd.read_csv(RESULTS / "final" / "h3_teammates_2025.csv").set_index("team_season")
    ferrari = teams_2025.loc["Ferrari 2025"]
    n["h3"]["ferrari_raw"] = f(ferrari["raw lap statistics | balanced_accuracy"], 2)
    n["h3"]["ferrari_ours"] = f(ferrari["our features | balanced_accuracy"], 2)

    # --- H4 driver vs car
    dev_sig = load("13_signature_stability/summary.json")
    explore = load("15_final_exploratory/summary.json")
    changers = pd.read_csv(RESULTS / "final" / "h4_changers.csv")
    n["h4"] = {
        "dev": {"mean_rank": f(dev_sig["corner_features"]["mean_own_rank"], 2),
                "chance_rank": f(dev_sig["corner_features"]["chance_mean_rank"], 0),
                # candidates in the ranking: chance mean rank = (candidates + 1) / 2
                "pool": int(round(2 * dev_sig["corner_features"]["chance_mean_rank"] - 1)),
                "rank_1": dev_sig["corner_features"]["rank_1_count"], "drivers": dev_sig["drivers_in_both_seasons"],
                "rank_p": p_text(dev_sig["corner_features"]["permutation_p"]),
                "own_closer": dev_sig["corner_features"]["own_closer_than_teammate"],
                "pairs": dev_sig["corner_features"]["pairs"], "p": p_text(dev_sig["corner_features"]["sign_test_p"]),
                "brake_share_own": dev_sig["share_braking"]["own_closer_than_teammate"],
                "brake_share_p": p_text(dev_sig["share_braking"]["sign_test_p"]),
                "brake_share_corr": f(dev_sig["share_braking"]["correlation_old_new"], 2)},
        "final": {"own_closer": final["h4"]["own_closer"], "changers": final["h4"]["changers_included"],
                  "p": p_text(final["h4"]["sign_test_p"]), "min_p": p_value(final["h4"]["min_possible_p"]),
                  "brake_share_own": final["h4"]["share_braking_own_closer"],
                  "brake_share_p": p_text(final["h4"]["share_braking_sign_test_p"]),
                  "stayers_own": final["non_changer_check"]["own_closer"],
                  "stayers": final["non_changer_check"]["drivers"],
                  "stayers_p": p_text(final["non_changer_check"]["sign_test_p"]),
                  "supported": final["h4_supported"],
                  "rows": [{"driver": r.driver, "team_2024": r.team_2024, "team_2025": r.team_2025,
                            "teammate": r.teammate_2025, "own": f(r.distance_own_2024, 2),
                            "mate": f(r.distance_new_teammate_2025, 2),
                            "closer": "own 2024" if r.own_closer else "new teammate",
                            "rank": int(r.own_rank_among_2024), "of": int(r.drivers_2024)}
                           for r in changers[changers["included"]].itertuples()]},
        "explore": {"with_col_own": explore["h4_with_all_changers"]["own_closer"],
                    "with_col_n": explore["h4_with_all_changers"]["changers_included"],
                    "with_col_p": p_text(explore["h4_with_all_changers"]["sign_test_p"]),
                    "control_own": explore["h4_shape_control_non_changers"]["own_closer"],
                    "control_n": explore["h4_shape_control_non_changers"]["changers_included"],
                    "control_p": p_text(explore["h4_shape_control_non_changers"]["sign_test_p"]),
                    "fisher_p": p_text(explore["changers_vs_stayers"]["fisher_exact_two_sided_p"]),
                    "stayers_no_col_own": explore["non_changer_check_without_changers"]["own_closer"],
                    "stayers_no_col_n": explore["non_changer_check_without_changers"]["drivers"],
                    "stayers_no_col_p": p_text(explore["non_changer_check_without_changers"]["sign_test_p"])},
    }
    # --- the per-lap position-offset check (experiment 18)
    offset = load("18_position_offset/summary.json")
    n["offset"] = {
        "laps": thousands(offset["laps_with_offset"]),
        "within_driver_sd_m": f(offset["q1_beyond_noise"]["median_within_driver_session_sd_m"], 1),
        "noise_floor_m": f(offset["q1_beyond_noise"]["noise_floor_m"], 2),
        "session_share": f(offset["q2_variance_share"]["sessions"] * 100, 0),
        "pairs": thousands(offset["q3_gap_error"]["pairs"]),
        "gap_slope": f(offset["q3_gap_error"]["slope_error_m_on_offset_difference"], 2),
        "leak_slope": f(offset["q4_feature_leakage"]["pooled_position_features"]["slope"], 3),
        "leak_low": f(offset["q4_feature_leakage"]["pooled_position_features"]["ci95"][0], 3),
        "leak_high": f(offset["q4_feature_leakage"]["pooled_position_features"]["ci95"][1], 3),
        "line_error_d_s": f(offset["q3_gap_error"]["median_abs_error_s_integrated"], 3),
        "line_error_s_s": f(offset["q3_gap_error"]["median_abs_error_s_projected"], 3),
    }
    n["prereg"] = {"part_a": pilot["preregistration_commit"][:7], "part_b": final["preregistration_commit"][:7]}

    # --- the repository: the highest experiment number, so the README never lists a stale range
    experiment_numbers = []
    for script in (REPO_ROOT / "experiments").glob("[0-9][0-9]_*.py"):
        experiment_numbers.append(int(script.name[:2]))
    n["repo"] = {"last_experiment": f"{max(experiment_numbers):02d}"}
    n["c"] = collect_part_c_numbers(n["prereg"])
    n["a1"] = collect_addendum_1_numbers()
    n["h5"] = collect_h5_numbers(n["c"])
    # attempt 1's diagnosis (experiment 25) and attempt 2's removal must count the same marker samples
    assert n["a1"]["either"] == n["h5"]["data"]["removed"], "markers diagnosed and markers removed differ"
    n["x26"] = collect_exploratory_2026(n["h5"])
    return n


def collect_exploratory_2026(h5):
    """The two EXPLORATORY follow-ups of Day 16 (docs/decisions.md, 2026-11-09): the laps lost to
    the marker removal (experiment 28) and teammate-relative signatures (experiment 29)."""
    lost = load("28_lost_laps_2026/summary.json")
    per_driver = pd.read_csv(RESULTS / "28_lost_laps_2026" / "per_driver.csv")
    assert lost["matches_download_logs"] and lost["lost"] == h5["data"]["laps_lost_to_markers"]
    sensitivity = lost["h5_sensitivity"]
    assert sensitivity["reproduced_frozen_table"]
    assert sensitivity["all_sessions"]["own_closer"] == h5["all"]["own"], "experiment 28 differs from the frozen test"
    worst = per_driver.sort_values("lost", ascending=False).iloc[0]
    x = {"lost": lost["lost"], "driver_sessions": int(len(per_driver)),
         "most": int(worst["lost"]), "most_driver": worst["driver"], "most_location": worst["location"],
         "most_kept": int(worst["kept"]),
         "whole_weekends": len(lost["whole_weekends_lost"]),
         "edges": lost["lost_by_reason"].get("start or end not bracketed by samples", 0),
         "thin": lost["lost_by_reason"].get("fewer than 10 car samples", 0),
         "usable": {name: f(share, 2) for name, share in lost["usable_share"]["marker_heavy"].items()},
         "usable_low": f(lost["usable_share"]["other_sessions_min"], 2),
         "usable_high": f(lost["usable_share"]["other_sessions_max"], 2),
         "left_out": " and ".join(sensitivity["without_marker_heavy"]["left_out"]),
         "without": f"{sensitivity['without_marker_heavy']['own_closer']} of {sensitivity['without_marker_heavy']['drivers']}",
         "changed": len(sensitivity["drivers_whose_answer_changed"]),
         # 5 decimals: rounding 0.000344 to 4 would print "0.0003", smaller than the true difference
         "largest_difference": f(sensitivity["largest_distance_difference_vs_frozen"], 5)}

    relative = load("29_teammate_relative/summary.json")
    pairs = pd.read_csv(RESULTS / "29_teammate_relative" / "pairs.csv")
    x["rel"] = {}
    for key, name in (("first", "2023 -> 2024"), ("second", "2024 -> 2025"), ("rules", "2025 -> 2026")):
        block = relative["comparisons"][name]
        x["rel"][key] = {"pairs": block["pairs"], "positive": block["cosine_positive"],
                         "median": f(block["median_cosine"], 2), "p": p_text(block["sign_test_p_orientation_only"]),
                         "split": f(block["median_split_half_earlier"], 2)}
    reversed_2026 = pairs[(pairs["comparison"] == "2025 -> 2026") & (pairs["cosine"] < 0)]
    x["rel"]["reversed"] = " and ".join(reversed_2026["pair"])
    x["rel"]["min_weekends"] = relative["min_weekends"]

    # drivers of the 2025 -> 2026 pairs whose first full season was 2025 (fewer than the minimum
    # weekends in the 2024 data): their difference may change with experience, not only the rules
    development, _ = clean(load_dataset())
    weekends_2024 = development[development["year"] == 2024].groupby("driver")["session_key"].nunique()
    in_2026_pairs = sorted(set(pairs.loc[pairs["comparison"] == "2025 -> 2026", "driver_a"])
                           | set(pairs.loc[pairs["comparison"] == "2025 -> 2026", "driver_b"]))
    newer = [driver for driver in in_2026_pairs if weekends_2024.get(driver, 0) < relative["min_weekends"]]
    x["rel"]["first_season_2025"] = ", ".join(newer)
    return x


def collect_h5_numbers(c):
    """The frozen 2026 test (results/final_2026/, run once on 2026-11-07) for the README and the report:
    H5, H4 on the 2026 team changers, the corner types, the data, and the re-check and exploratory pair
    counts of experiment 27. Nothing is recomputed here except counts read off the frozen files."""
    from apextrace.signatures import sign_test_power, sign_test_threshold

    final = load("final_2026/summary.json")
    checks = load("final_2026/checks.json")
    attempt_1 = load("final_2026_attempt_1/run_started.json")
    figures = load("27_final_2026_figures/summary.json")
    assert figures["all_match"], "experiment 27 found a frozen 2026 number that does not match its table"
    sessions = pd.read_csv(RESULTS / "final_2026" / "sessions_2026.csv")
    h5_table = pd.read_csv(RESULTS / "final_2026" / "h5_all.csv")
    changes = pd.read_csv(RESULTS / "final_2026" / "team_changes.csv")

    def block_numbers(block):
        return {"own": block["own_closer"], "n": block["drivers"], "share": f(block["share"], 2),
                "low": f(block["ci95_low"], 2), "high": f(block["ci95_high"], 2), "p": p_text(block["sign_test_p"])}

    sets = final["h5"]["sets"]
    primary = sets["all"]
    drivers = primary["drivers"]
    h5 = {"verdict": final["h5"]["verdict"], "supported": final["h5"]["supported"],
          "all": block_numbers(primary), "control": block_numbers(sets["control points"]),
          "energy": block_numbers(sets["energy-sensitive"]), "no_throttle": block_numbers(sets["no throttle"]),
          "features": final["h5"]["features"], "needed": sign_test_threshold(drivers),
          "commits": {"part_c": attempt_1["preregistration_commit"][:7],
                      "addendum_1": final["preregistration_commit"][:7]},
          "null": c["null"], "smallest_testable": c["smallest_testable"]}
    assert final["checks_ok"] and h5["verdict"] in ("supported", "not supported", "not testable")

    # the same comparison without a rule change (experiment 20, the numbers Part C quotes)
    development = load("20_h5_development/summary.json")["pairs"]
    h5["dev"] = {"first": block_numbers(development["2023 -> 2024"]["all"]),
                 "second": block_numbers(development["2024 -> 2025"]["all"])}

    # power with this many drivers: at the development rates, and at a weakened rate
    rates = [development[key]["all"]["share"] for key in ("2023 -> 2024", "2024 -> 2025")]
    h5["power_dev_low"] = f(sign_test_power(drivers, min(rates)) * 100, 0)
    h5["power_dev_high"] = f(sign_test_power(drivers, max(rates)) * 100, 0)
    h5["power_70"] = f(sign_test_power(drivers, 0.7) * 100, 0)
    h5["power_85"] = f(sign_test_power(drivers, 0.85) * 100, 0)
    null = load("22_h5_null_check/summary.json")["cases"]
    h5["null_pair_inside"] = f(null["B pair inside the spread"]["share"], 2)

    # the smallest margin (a near tie), so a reader who counts the bars in the figure is not misled
    margins = (h5_table["distance_teammate"] - h5_table["distance_own"]).abs()
    tie = h5_table.loc[margins.idxmin()]
    h5["tie_driver"], h5["tie_margin"] = tie["driver"], f(margins.min(), 3)

    # which 2026 drivers were not compared, and why (the rule: at least MIN_WEEKENDS in both seasons)
    from apextrace import h5_protocol

    rows_2026, _ = clean(pd.read_csv(RESULTS / "final_2026" / "dataset_2026.csv.gz"))
    rows_2025, _ = clean(pd.read_csv(RESULTS / "final" / "dataset_2025.csv.gz"))
    weekends_2026 = rows_2026.groupby("driver")["session_key"].nunique()
    weekends_2025 = rows_2025.groupby("driver")["session_key"].nunique()
    no_2025, few_2026 = [], []
    for driver in sorted(set(weekends_2026.index) - set(h5_table["driver"])):
        if weekends_2025.get(driver, 0) < h5_protocol.MIN_WEEKENDS:
            # the report says "no 2025 qualifying data": true only if there is none at all
            assert weekends_2025.get(driver, 0) == 0, f"{driver} has some 2025 weekends: change the report's wording"
            no_2025.append(driver)
        else:
            assert weekends_2026[driver] < h5_protocol.MIN_WEEKENDS, f"{driver}: not compared for another reason"
            few_2026.append(f"{driver} with {weekends_2026[driver]}")
    h5["drivers_2026"] = int(len(weekends_2026))
    h5["not_compared"] = {"no_2025": ", ".join(no_2025), "few_2026": ", ".join(few_2026),
                          "min_weekends": h5_protocol.MIN_WEEKENDS}

    # H4 on the 2026 team changers (secondary, descriptive with one changer)
    h4 = final["h4"]
    changer = pd.read_csv(RESULTS / "final_2026" / "h4_changers.csv")
    changer = changer[changer["included"] == True]  # noqa: E712
    not_eligible = changes[changes["changed"] & ~changes["eligible"]]
    h5["h4"] = {"changers": block_numbers(h4["changers"]), "stayers": block_numbers(h4["stayers"]),
                "test_possible": h4["changers"]["test_possible"], "fisher_p": p_text(h4["fisher_exact_two_sided_p"]),
                "rows": [{"driver": r.driver, "before": r.team_reference, "after": r.team_target,
                          "teammate": r.teammate_target, "own": f(r.distance_own_reference, 2),
                          "mate": f(r.distance_new_teammate, 2),
                          "closer": "own 2025" if r.own_closer else "new teammate"} for r in changer.itertuples()],
                "not_eligible": [{"driver": r.driver, "before": r.team_reference, "after": r.team_target,
                                  "weekends": int(r.weekends_target)} for r in not_eligible.itertuples()],
                "dev_stayers_first": c["h4"]["stayers_first"], "dev_stayers_second": c["h4"]["stayers_second"]}

    corner_types = {}
    for year, counts in final["corner_types"].items():
        corner_types[year] = {kind: f(value["per_session"], 2) for kind, value in counts.items()}
    h5["corners"] = corner_types

    # laps whose car data became unusable once the 104 samples were removed (Addendum 1): a lap needs
    # at least 10 car samples and samples on both sides of its start and end (openf1.slice_lap).
    # Attempt 1 counted laps with data WITHOUT the rule, attempt 2 WITH it; same sessions, same laps.
    log_1 = pd.read_csv(RESULTS / "final_2026_attempt_1" / "download_log.csv").set_index("session_key")
    log_2 = pd.read_csv(RESULTS / "final_2026" / "download_log.csv").set_index("session_key")
    assert log_1["kept_laps"].equals(log_2["kept_laps"]), "the two attempts kept different laps"
    lost = (log_1["kept_laps_with_data"] - log_2["kept_laps_with_data"]).sort_values(ascending=False)
    assert (lost >= 0).all(), "removing samples can only lose laps"
    lost_text = []
    for session_key, count in lost[lost > 0].items():
        lost_text.append(f"{log_2.loc[session_key, 'location']} {int(count)}")

    built = sessions[sessions["laps"] > 0]
    removed = sum(s["no_value_removed"] for s in checks["no_value_marker_removed"])
    samples = sum(s["samples"] for s in checks["no_value_marker_removed"])
    h5["data"] = {"listed": len(final["sessions"]), "built": int(len(built)),
                  "empty": " and ".join(sessions.loc[sessions["laps"] == 0, "location"]),
                  "last": final["sessions"][-1]["location"], "cutoff": final["cutoff_utc"].replace("T", " ")[:16] + " UTC",
                  "laps_kept": thousands(built["kept_laps"].sum()), "lap_vectors": thousands(final["laps"]),
                  "laps_with_data": thousands(log_2["kept_laps_with_data"].sum()),
                  "laps_lost_to_markers": int(lost.sum()), "laps_lost_where": ", ".join(lost_text),
                  "usable": thousands(final["cleaning"]["usable_rows"]), "clean": thousands(final["cleaning"]["clean_rows"]),
                  "sessions_clean": int(rows_2026["session_key"].nunique()),
                  "removed": thousands(removed), "removed_share": f(removed / samples * 100, 2)}
    assert h5["data"]["clean"] == thousands(len(rows_2026)), "the 2026 cleaning differs from summary.json"

    # EXPLORATORY (experiment 27): how the pairs of 2025 teammates came out, and the drivers whose
    # 2025 teammate was not compared. The 13 = split pairs + 2 x pairs both "own" + the singles' own.
    pairs = figures["exploratory_teammate_pairs"]
    compared = set(h5_table["driver"])
    singles = h5_table[~h5_table["teammate"].isin(compared)]
    h5["pairs"] = {"n": pairs["pairs"], "split": pairs["split"], "both_own": pairs["both_own_past"],
                   "both_own_drivers": 2 * pairs["both_own_past"], "both_mate": pairs["both_teammate"],
                   "singles": ", ".join(f"{r.driver} (2025 teammate {r.teammate})" for r in singles.itertuples()),
                   "singles_own": int(singles["own_closer"].sum())}
    assert (pairs["split"] + 2 * pairs["both_own_past"] + h5["pairs"]["singles_own"]) == primary["own_closer"]
    return h5


def collect_addendum_1_numbers():
    """Every number in Addendum 1 to Part C: the diagnosis of the failed feed check
    (experiment 25) and the dry run with the new rule (experiment 26)."""
    diagnosis = load("25_feed_check_2026_diagnosis/summary.json")
    check = load("26_addendum_1_dry_run_check/summary.json")
    total = diagnosis["samples_inside_kept_laps"]
    either = sum(session["samples_with_either"] for session in diagnosis["sessions"])
    sessions = sorted([s for s in diagnosis["sessions"] if s["samples"]], key=lambda s: -s["share_with_either"])
    worst = [f"{s['session']} {f(s['share_with_either'] * 100, 1)} %" for s in sessions[:3]]
    rest = max(s["share_with_either"] for s in sessions[3:])
    development = []
    for year, counts in sorted(diagnosis["development_throttle_marker"].items()):
        development.append(f"{year} {f(counts['throttle_104'] / counts['samples'] * 100, 3)} %")
    empty_sessions = [s["session"] for s in diagnosis["sessions"] if not s["samples"]]
    a1 = {"samples": thousands(total), "throttle": thousands(diagnosis["throttle_out_of_range_values"]["104.0"]),
          "brake": thousands(diagnosis["brake_out_of_range_values"]["104.0"]), "either": thousands(either),
          "either_share": f(either / total * 100, 2), "worst": ", ".join(worst), "rest": f(rest * 100, 2),
          "development": ", ".join(development), "empty_sessions": " and ".join(empty_sessions),
          "other_values": (set(diagnosis["throttle_out_of_range_values"]) | set(diagnosis["brake_out_of_range_values"]))
          == {"104.0"},
          "dry_rows": thousands(check["rows_rebuilt"]), "dry_changed": thousands(check["rows_changed"]),
          "dry_usable_original": thousands(check["usable_original"]),
          "dry_usable_rebuilt": thousands(check["usable_rebuilt"]),
          "dry_removed": thousands(check["marker_samples_removed"]), "dry_checks_ok": check["checks_ok"],
          "dry_h5": f"{check['h5_dry_run']['own_closer']} of {check['h5_dry_run']['drivers']}",
          "dry_h5_same": check["h5_same_count"]}
    assert a1["other_values"], "the diagnosis found an out-of-range value other than 104"
    return a1


# ---------------------------------------------------------------- preregistration Part C (the 2026 test)

def count_text(block):
    """A sign-test block -> '16 of 20 (0.80, 95 % interval 0.56–0.94)'."""
    return (f"{block['own_closer']} of {block['drivers']} ({f(block['share'], 2)}, 95 % interval "
            f"{f(block['ci95_low'], 2)}–{f(block['ci95_high'], 2)})")


def collect_part_c_numbers(prereg):
    """Every number and rule value in preregistration Part C, from results files or from the code
    itself (the feed rules, the team map, the feature groups, the script's constants), so the plan
    can't disagree with the code that runs it."""
    import importlib.util

    from apextrace import corners, dataset, h5_protocol, quality, teams
    from apextrace.identification import CORNER_TYPES, FEATURE_GROUPS
    from apextrace.signatures import sign_test_power, sign_test_threshold

    spec = importlib.util.spec_from_file_location("final_2026", REPO_ROOT / "experiments" / "23_final_2026.py")
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    c = {"written": "2026-11-06", "commits": prereg, "disclosure": PART_C_DISCLOSURE,
         "script": {"switch": script.SWITCH, "cutoff_hours": script.CUTOFF_HOURS,
                    "min_weekends": h5_protocol.MIN_WEEKENDS, "retries": script.DOWNLOAD_RETRIES,
                    "cutoff": f"{script.CUTOFF_UTC:%Y-%m-%d %H:%M} UTC",
                    "run_from": f"{script.CUTOFF_UTC + timedelta(hours=script.CUTOFF_HOURS):%Y-%m-%d %H:%M} UTC"},
         "rules": {"slow_below": f(corners.SLOW_BELOW_KMH, 0), "fast_from": f(corners.FAST_FROM_KMH, 0),
                   "min_speed": f(dataset.MIN_PLAUSIBLE_SPEED_KMH, 0)}}

    rules = quality.FEED_RULES
    c["feed"] = {"median_low": f(rules["median_interval_s"][0], 2), "median_high": f(rules["median_interval_s"][1], 2),
                 "grid_min": f(rules["on_40ms_grid_min"] * 100, 0), "rate_low": f(rules["rate_hz"][0], 1),
                 "rate_high": f(rules["rate_hz"][1], 1), "missing_max": f(rules["missing_max"] * 100, 0),
                 "in_range_min": f(rules["in_range_min"] * 100, 1)}
    labels = {"speed": ("speed", "km/h"), "throttle": ("throttle", "%"), "n_gear": ("gear", "")}
    ranges = []
    for name, value_range in quality.CAR_CHANNELS.items():
        if value_range is None:
            ranges.append(f"{name} only 0 or 100")
        else:
            label, unit = labels[name]
            ranges.append(f"{label} {value_range[0]}–{value_range[1]}{(' ' + unit) if unit else ''}")
    c["feed"]["ranges"] = ", ".join(ranges)
    checks_2024 = load("final_2026_dry_run/2024/checks.json")["feed"]["checks"]
    c["feed_2024"] = {"median": f(checks_2024["median interval (s)"]["value"], 3),
                      "grid": f(checks_2024["on the 40 ms clock"]["value"] * 100, 2),
                      "rate": f(checks_2024["samples per second"]["value"], 2),
                      "throttle": f(checks_2024["throttle values"]["value"] * 100, 2),
                      "brake": f(checks_2024["brake values"]["value"] * 100, 2)}
    c["compounds"] = {"known": ", ".join(sorted(dataset.KNOWN_COMPOUNDS)), "dry": ", ".join(sorted(dataset.DRY_COMPOUNDS)),
                      "max_empty": f(dataset.MAX_EMPTY_COMPOUND_SHARE * 100, 0)}
    # a "|" inside a Markdown table cell would split the cell, so it is escaped
    c["lineages"] = [{"lineage": lineage, "patterns": pattern.replace("|", "\\|")}
                     for pattern, lineage in teams.LINEAGE_PATTERNS]

    every_feature = [feature for group in FEATURE_GROUPS.values() for feature in group]
    columns = [f"{feature}_rel__{corner}" for feature in every_feature for corner in CORNER_TYPES]
    sets = h5_protocol.feature_sets(columns)
    c["sets"] = {"all": len(sets["all"]), "control": len(sets["control points"]), "energy": len(sets["energy-sensitive"]),
                 "no_throttle": len(sets["no throttle"])}
    c["names"] = {"control": ", ".join(f"`{name}`" for name in h5_protocol.CONTROL_POINTS),
                  "energy": ", ".join(f"`{name}`" for name in h5_protocol.ENERGY_SENSITIVE),
                  "throttle": ", ".join(f"`{name}`" for name in h5_protocol.THROTTLE)}

    c["eligible_upper"] = load("19_h5_power/summary.json")["eligible_upper_bound"]
    needed = []
    for drivers in range(8, 22):
        needed.append(f"{drivers} → {sign_test_threshold(drivers)}")
    c["needed"] = ", ".join(needed)
    smallest_testable = 1
    while sign_test_threshold(smallest_testable) is None:
        smallest_testable += 1
    c["smallest_testable"] = smallest_testable              # 5: with 4 drivers even 4 of 4 gives p = 0.0625
    c["q_values"] = [0.6, 0.7, 0.8, 0.85, 0.9]
    c["power_rows"] = []
    for drivers in (12, 14, 16, 18, 20, 21):
        c["power_rows"].append({"n": drivers, "needed": sign_test_threshold(drivers),
                                "powers": [f(sign_test_power(drivers, q), 2) for q in c["q_values"]]})
    changers = []
    for count in range(3, 9):
        threshold = sign_test_threshold(count)
        changers.append(f"{count} changers: {'no p < 0.05 possible' if threshold is None else f'{threshold} needed'}")
    c["changers_needed"] = "; ".join(changers)

    development = load("20_h5_development/summary.json")["pairs"]
    c["dev"] = {}
    for key, label in (("first", "2023 -> 2024"), ("second", "2024 -> 2025")):
        pair = development[label]
        c["dev"][key] = {"text": count_text(pair["all"]),
                         "control": count_text(pair["variants"]["control points"]),
                         "energy": count_text(pair["variants"]["energy-sensitive"]),
                         "no_throttle": count_text(pair["variants"]["no throttle"])}
        powers = list(pair["power_if_2026_had_this_rate"].values())
        if min(powers) >= 0.99:          # "99-100 %" would overstate a rounded 0.996
            c["dev"][f"power_{key}"] = f"{f(min(powers) * 100, 0)} % or more"
        else:
            c["dev"][f"power_{key}"] = f"{f(min(powers) * 100, 0)}–{f(max(powers) * 100, 0)} %"

    dry_2024 = load("final_2026_dry_run/2024/summary.json")
    dry_2025 = load("final_2026_dry_run/2025/summary.json")
    stayers = [dry_2024["h4"]["stayers"], dry_2025["h4"]["stayers"]]
    c["h4"] = {"stayers_first": f"{stayers[0]['own_closer']} of {stayers[0]['drivers']}",
               "stayers_second": f"{stayers[1]['own_closer']} of {stayers[1]['drivers']}"}

    coasting = load("21_coasting_check/summary.json")
    table = pd.read_csv(RESULTS / "21_coasting_check" / "error_table.csv")
    gaps = []
    for car in ("", "2026-like + "):
        without = "Phase 2 car" if car == "" else "2026-like car"
        for corner_type in table["corner_type"].unique():
            lift = table[(table["scenario"] == f"{car}lift and coast") & (table["corner_type"] == corner_type)]
            plain = table[(table["scenario"] == without) & (table["corner_type"] == corner_type)]
            gaps.append(float(plain["chosen_bias_m"].iloc[0] - lift["chosen_bias_m"].iloc[0]))
    c["coasting"] = {"worst": f(coasting["worst"]["rmse_m"], 2), "threshold": f(coasting["threshold_m"], 1),
                     "gap_low": f(min(gaps), 1), "gap_high": f(max(gaps), 1)}

    null = load("22_h5_null_check/summary.json")
    whole = null["G whole test under the null"]
    c["null"] = {"all_laps": f(null["cases"]["E all laps, teammate with fewer laps"]["share"], 2),
                 "equal_laps": f(null["cases"]["F H5 rules, teammate with fewer laps"]["share"], 2),
                 "laps_lead": null["setup_laps"]["laps_lead"], "laps_second": null["setup_laps"]["laps_second"],
                 "false_positive": f(whole["false_positive_rate"], 3), "studies": whole["studies"],
                 "drivers": whole["drivers_per_study"], "variance": f(whole["count_variance"], 2),
                 "binomial_variance": f(whole["binomial_variance"], 2),
                 "split": f(whole["pairs_split_one_and_one"] * 100, 0),
                 "conservative": whole["false_positive_rate"] <= 0.05}

    checks = load("24_dry_run_checks/summary.json")
    primary_2024, primary_2025 = dry_2024["h5"]["sets"]["all"], dry_2025["h5"]["sets"]["all"]
    c["dry"] = {"rows": thousands(checks["rebuild_2024"]["rows_rebuilt"]),
                "largest": f(checks["rebuild_2024"]["largest_feature_difference"], 1),
                "h5_2024": f"{primary_2024['own_closer']} of {primary_2024['drivers']}",
                "h5_2025": f"{primary_2025['own_closer']} of {primary_2025['drivers']}",
                "h4_drivers": checks["frozen_h4_2025"]["changers"]["drivers"] + checks["frozen_h4_2025"]["stayers"]["drivers"]}
    assert checks["rebuild_2024"]["identical"] and checks["frozen_h4_2025"]["all_match"], "a dry-run check failed"
    assert dry_2024["matches_experiment_20"] and dry_2025["matches_experiment_20"], "a dry run differs from experiment 20"
    return c


# Who saw what of the 2026 season before Part C was written: the author's own words (2026-11-06).
PART_C_DISCLOSURE = ("\"I know the driver line-up and which drivers changed teams, but not much about results. "
                     "I know Kimi won this year's F1 title in Mexico.\" None of this is used in the design: team "
                     "changers are found from the data by a fixed rule (`teams.team_changers`), and no rule depends "
                     "on any driver's 2026 results.")
PART_C_TEMPLATE = "preregistration_part_c.md.j2"
PREREGISTRATION = REPO_ROOT / "docs" / "preregistration.md"
PART_C_START = ("<!-- Part C below is generated by experiments/17_write_docs.py from "
                "docs/templates/preregistration_part_c.md.j2: edit the template, not this text. -->")
PART_C_END = "<!-- end of Part C -->"


ADDENDUM_1_TEMPLATE = "preregistration_part_c_addendum_1.md.j2"
ADDENDUM_1_START = ("<!-- Addendum 1 to Part C below is generated by experiments/17_write_docs.py from "
                    "docs/templates/preregistration_part_c_addendum_1.md.j2: edit the template, not this text. -->")
ADDENDUM_1_END = "<!-- end of Addendum 1 -->"


def committed_block(start, end):
    """The block between two markers in the last commit (HEAD), or None if it isn't committed yet."""
    import subprocess

    result = subprocess.run(["git", "show", "HEAD:docs/preregistration.md"], cwd=REPO_ROOT, capture_output=True,
                            text=True, encoding="utf-8")
    if result.returncode != 0 or start not in result.stdout:
        return None
    tail = result.stdout.replace("\r\n", "\n").split(start, 1)[1]
    if end not in tail:
        return None
    return start + tail.split(end, 1)[0] + end + "\n"


def write_block(start, end, rendered, separator=""):
    """Put one generated block (Part C, or an addendum) into docs/preregistration.md, replacing only
    the text between its own markers; everything before and after is kept exactly as it is. A new
    block is added at the end of the file, after `separator`.

    Once a block is committed it is FROZEN: if the rendered text would differ from the committed one
    (say, a development result was re-run), nothing is written and the script stops. A frozen plan
    can't be rewritten by re-running a script."""
    block = start + "\n\n" + rendered + "\n" + end + "\n"
    frozen = committed_block(start, end)
    if frozen is not None and frozen != block:
        raise SystemExit("A committed, frozen block of the preregistration would change. Nothing was written. "
                         "Find what changed (a results file or the template); a change to a committed plan is a "
                         "deviation (docs/preregistration_deviations.md).")
    text = PREREGISTRATION.read_text(encoding="utf-8").replace("\r\n", "\n")
    if start in text:
        before, rest = text.split(start, 1)
        after = rest.split(end, 1)[1].lstrip("\n") if end in rest else ""
        new = before + block + ("\n" + after if after else "")
    else:
        new = text.rstrip("\n") + "\n\n" + separator + block
    PREREGISTRATION.write_text(new, encoding="utf-8", newline="\n")


def write_part_c(rendered):
    """Part C at the end of the file after Parts A and B (which are never rewritten)."""
    write_block(PART_C_START, PART_C_END, rendered, separator="---\n\n")


def write_addendum_1(rendered):
    """Addendum 1, right after Part C."""
    write_block(ADDENDUM_1_START, ADDENDUM_1_END, rendered)


def main():
    numbers = collect_numbers()
    environment = Environment(loader=FileSystemLoader(TEMPLATES), undefined=StrictUndefined,
                              keep_trailing_newline=True, autoescape=False)
    for template_name, output in OUTPUTS.items():
        text = environment.get_template(template_name).render(**numbers)
        notice = (f"<!-- Generated by experiments/17_write_docs.py from docs/templates/{template_name}: "
                  "edit the template, not this file. Every number comes from results/. -->\n")
        output.write_text(notice + text, encoding="utf-8", newline="\n")
        print(f"wrote {output.relative_to(REPO_ROOT)} ({len(text.split())} words)")
    part_c = environment.get_template(PART_C_TEMPLATE).render(**numbers)
    write_part_c(part_c)
    print(f"wrote Part C into {PREREGISTRATION.relative_to(REPO_ROOT)} ({len(part_c.split())} words)")
    addendum = environment.get_template(ADDENDUM_1_TEMPLATE).render(**numbers)
    write_addendum_1(addendum)
    print(f"wrote Addendum 1 into {PREREGISTRATION.relative_to(REPO_ROOT)} ({len(addendum.split())} words)")
    with open(RESULTS / "report_numbers.json", "w", encoding="utf-8") as file:
        json.dump(numbers, file, indent=1, ensure_ascii=False)
    print("wrote results/report_numbers.json (every number the documents can use)")


if __name__ == "__main__":
    main()
