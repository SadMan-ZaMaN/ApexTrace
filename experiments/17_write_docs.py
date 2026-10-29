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
        "drivers_total": headline["drivers"],
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
    return n


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
    with open(RESULTS / "report_numbers.json", "w", encoding="utf-8") as file:
        json.dump(numbers, file, indent=1, ensure_ascii=False)
    print("wrote results/report_numbers.json (every number the documents can use)")


if __name__ == "__main__":
    main()
