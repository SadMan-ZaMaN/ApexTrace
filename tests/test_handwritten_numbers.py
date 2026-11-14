"""Hand-written documents that quote numbers: docs/sources.md, docs/ml_plan.md and the READMEs of
the two frozen tests (results/final/README.md, results/final_2026/README.md). Like test_design_numbers.py for
h5_design.md: every quoted number is rebuilt from the committed results files and the exact
phrase must be in the document. If a number goes stale or is mistyped, this fails.
Reads only committed files; no F1 data is downloaded.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from apextrace.signatures import sign_test_threshold

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"


def load(relative):
    return json.loads((RESULTS / relative).read_text(encoding="utf-8"))


def text_of(relative):
    return (REPO_ROOT / relative).read_text(encoding="utf-8").replace("\r\n", "\n")


def expect(document, name, phrase, source):
    """Whitespace is collapsed on both sides, so a line break inside a quoted phrase doesn't matter."""
    flat_document = " ".join(document.split())
    flat_phrase = " ".join(phrase.split())
    assert flat_phrase in flat_document, f"{name} should contain {flat_phrase!r} (from {source})"


def p_text(p):
    return f"p = {p:.2g}"


# ---------------------------------------------------------------- docs/sources.md

@pytest.fixture(scope="module")
def sources():
    return text_of("docs/sources.md")


def test_sessions_listed_and_with_data(sources):
    log = pd.read_csv(RESULTS / "08_download" / "download_log.csv")
    expect(sources, "sources.md", f"{len(log)} listed, {int((log['laps'] > 0).sum())} with data", "08 download log")
    s2025 = pd.read_csv(RESULTS / "final" / "sessions_2025.csv")
    expect(sources, "sources.md", f"{len(s2025)} listed, {int((s2025['laps'] > 0).sum())} with data", "sessions_2025")
    s2026 = pd.read_csv(RESULTS / "final_2026" / "sessions_2026.csv")
    expect(sources, "sources.md", f"{len(s2026)} listed, {int((s2026['laps'] > 0).sum())} with data", "sessions_2026")
    empty = " and ".join(s2026.loc[s2026["laps"] == 0, "location"])
    expect(sources, "sources.md", f"({empty} have no lap rows)", "sessions_2026")
    started = load("final_2026/run_started.json")
    expect(sources, "sources.md", f"ended before {started['cutoff_utc'][:10]} {started['cutoff_utc'][11:16]} UTC",
           "run_started.json")


def test_laps_per_season(sources):
    log = pd.read_csv(RESULTS / "08_download" / "download_log.csv")
    for year, rows in log.groupby("year"):
        expect(sources, "sources.md", f"| {year} | {rows['laps'].sum():,} | {rows['kept_laps'].sum():,} |", "08 log")
    s2025 = pd.read_csv(RESULTS / "final" / "sessions_2025.csv")
    expect(sources, "sources.md", f"| 2025 | {s2025['laps'].sum():,} | {s2025['kept_laps'].sum():,} |", "sessions_2025")
    s2026 = pd.read_csv(RESULTS / "final_2026" / "sessions_2026.csv")
    log2026 = pd.read_csv(RESULTS / "final_2026" / "download_log.csv")
    expect(sources, "sources.md", f"| {s2026['laps'].sum():,} | {s2026['kept_laps'].sum():,} "
                                  f"({log2026['kept_laps_with_data'].sum():,} with usable car data", "2026 files")


def test_cleaning_table(sources):
    dataset = load("09_dataset/summary.json")
    development = load("10_eda/summary.json")["cleaning"]
    final_2025 = load("final/summary.json")["cleaning_2025"]
    final_2026 = load("final_2026/summary.json")["cleaning"]
    expect(sources, "sources.md", f"| Rows (driver, lap, corner) | {dataset['rows']:,} |", "09_dataset")
    expect(sources, "sources.md", f"| {development['usable_rows']:,} | {final_2025['usable_rows']:,} | "
                                  f"{final_2026['usable_rows']:,} |", "cleaning summaries")
    expect(sources, "sources.md", f"| Dropped: not dry | {development['dropped_not_dry']:,} | "
                                  f"{final_2025['dropped_not_dry']:,} | {final_2026['dropped_not_dry']:,} |", "cleaning")
    expect(sources, "sources.md", f"| **{development['clean_rows']:,}** | **{final_2025['clean_rows']:,}** | "
                                  f"**{final_2026['clean_rows']:,}** |", "cleaning summaries")


def test_download_time_and_sample_rate(sources):
    log = pd.read_csv(RESULTS / "08_download" / "download_log.csv")
    expect(sources, "sources.md", f"took {log['seconds'].sum() / 60:.0f} min (~{log['seconds'].median():.0f} s per session)",
           "08 download log")
    rate = load("01_data_pilot/summary.json")["check_1_sample_timing"]["car"]["rate_from_mean_hz"]
    expect(sources, "sources.md", f"about {rate:.2f} times a second", "01_data_pilot")


# ---------------------------------------------------------------- results/final/README.md (2025)

def test_final_2025_readme():
    readme = text_of("results/final/README.md")
    summary = load("final/summary.json")
    h3 = summary["h3"]
    primary = h3["ours minus lap time only"]
    expect(readme, "final/README.md", f"on {primary['team_seasons']} teams", "summary h3")
    expect(readme, "final/README.md", f"balanced accuracy {h3['our features | balanced_accuracy']['mean']:.3f} vs "
                                      f"{h3['lap time only | balanced_accuracy']['mean']:.3f}", "summary h3")
    expect(readme, "final/README.md", f"in {primary['wins']} of {primary['team_seasons']} teams, Wilcoxon "
                                      f"{p_text(primary['wilcoxon_p'])}", "summary h3")
    raw = h3["ours minus raw lap statistics"]
    expect(readme, "final/README.md", f"({h3['raw lap statistics | balanced_accuracy']['mean']:.3f}; "
                                      f"p = {raw['wilcoxon_p']:.1f})", "summary h3")
    h4 = summary["h4"]
    expect(readme, "final/README.md", f"for {h4['own_closer']} of {h4['changers_included']} team changers", "summary h4")
    expect(readme, "final/README.md", f"p = {h4['sign_test_p']:.2f}.", "summary h4")
    changers = pd.read_csv(RESULTS / "final" / "h4_changers.csv")
    names = {"HUL": "Hülkenberg", "TSU": "Tsunoda", "HAM": "Hamilton", "SAI": "Sainz", "OCO": "Ocon"}
    closer = [names[d] for d in changers.loc[changers["own_closer"] == True, "driver"]]  # noqa: E712
    expect(readme, "final/README.md", f"({', '.join(closer)})", "h4_changers.csv")
    assert summary["h3_supported"] and not summary["h4_supported"]
    expect(readme, "final/README.md", "**H3 is replicated:**", "h3_supported")
    expect(readme, "final/README.md", "**H4 is not supported:**", "h4_supported")


# ---------------------------------------------------------------- results/final_2026/README.md

def test_final_2026_readme():
    readme = text_of("results/final_2026/README.md")
    summary = load("final_2026/summary.json")
    checks = load("final_2026/checks.json")
    primary = summary["h5"]["sets"]["all"]
    expect(readme, "final_2026/README.md", f"**H5 is {summary['h5']['verdict']}.**", "summary h5")
    expect(readme, "final_2026/README.md", f"{primary['own_closer']} of {primary['drivers']} drivers'", "summary h5")
    expect(readme, "final_2026/README.md", f"(share {primary['share']:.2f}, exact 95 % interval "
                                           f"{primary['ci95_low']:.2f}–{primary['ci95_high']:.2f})", "summary h5")
    expect(readme, "final_2026/README.md", f"gives p = {primary['sign_test_p']:.3f}, and "
                                           f"{sign_test_threshold(primary['drivers'])} of {primary['drivers']}", "h5")
    sets = summary["h5"]["sets"]
    expect(readme, "final_2026/README.md",
           f"(control points {sets['control points']['own_closer']}, energy-sensitive "
           f"{sets['energy-sensitive']['own_closer']}, no throttle {sets['no throttle']['own_closer']} of\n"
           f"{sets['no throttle']['drivers']})", "summary h5 sets")
    development = load("20_h5_development/summary.json")["pairs"]
    first, second = development["2023 -> 2024"]["all"], development["2024 -> 2025"]["all"]
    expect(readme, "final_2026/README.md", f"gave {first['own_closer']} of {first['drivers']} (2023 → 2024) and "
                                           f"{second['own_closer']} of {second['drivers']} (2024 → 2025)", "20")
    h4 = summary["h4"]
    expect(readme, "final_2026/README.md", f"({h4['changer_names'][0]}, Racing Bulls → Red Bull Racing)", "h4")
    expect(readme, "final_2026/README.md", f"({h4['changers']['own_closer']} of {h4['changers']['drivers']})", "h4")
    expect(readme, "final_2026/README.md", f"gave {h4['stayers']['own_closer']} of {h4['stayers']['drivers']}", "h4")
    corners = summary["corner_types"]
    expect(readme, "final_2026/README.md", f"({corners['2026']['fast']['per_session']:.2f} against "
                                           f"{corners['2025']['fast']['per_session']:.2f})", "corner types")
    expect(readme, "final_2026/README.md", f"({corners['2026']['slow']['per_session']:.2f} against "
                                           f"{corners['2025']['slow']['per_session']:.2f})", "corner types")
    removed = sum(s["no_value_removed"] for s in checks["no_value_marker_removed"])
    expect(readme, "final_2026/README.md", f"({removed:,}\nmarker samples removed)", "checks.json")
    sessions = pd.read_csv(RESULTS / "final_2026" / "sessions_2026.csv")
    expect(readme, "final_2026/README.md", f"{int((sessions['laps'] > 0).sum())} sessions built", "sessions_2026")
    expect(readme, "final_2026/README.md", f"{summary['laps']:,}\n  laps", "summary laps")
    expect(readme, "final_2026/README.md", f"all {len(summary['sessions'])} sessions", "summary sessions")
    diagnosis = load("25_feed_check_2026_diagnosis/summary.json")
    either = sum(s["samples_with_either"] for s in diagnosis["sessions"])
    expect(readme, "final_2026/README.md", f"{either / diagnosis['samples_inside_kept_laps'] * 100:.2f} % of throttle",
           "25 diagnosis")


# ---------------------------------------------------------------- docs/ml_plan.md

def conv_weights(filters, channels, length):
    """A 1-D convolution has filters x channels x length coefficients plus one bias per filter."""
    return filters * channels * length + filters


def test_ml_plan_numbers():
    from apextrace.corners import GAP_S, WINDOW_AFTER_M, WINDOW_BEFORE_M
    from apextrace.dataset import MIN_PLAUSIBLE_SPEED_KMH
    from apextrace.identification import ALL_FEATURES, CORNER_TYPES, RAW_STATS

    plan = text_of("docs/ml_plan.md")
    name = "ml_plan.md"

    # The input: the features' own window, gap rule and cleaning.
    expect(plan, name, f"no interval longer than {GAP_S:g} s between samples", "corners.GAP_S")
    expect(plan, name, f"minimum speed at least {MIN_PLAUSIBLE_SPEED_KMH:g} km/h", "dataset.MIN_PLAUSIBLE_SPEED_KMH")
    step_m = 5
    points = int((WINDOW_BEFORE_M + WINDOW_AFTER_M) / step_m) + 1
    expect(plan, name, f"from {WINDOW_BEFORE_M:g} m before to {WINDOW_AFTER_M:g} m after the corner marker, "
                       f"every {step_m} m ({points} points)", "corners.WINDOW_*_M")
    channels = 4
    expect(plan, name, f"the {channels} × {points} grid", "the input section")

    # The model's weight count: the arithmetic in the table, from the design.
    first, second, length = 8, 16, 5
    summary_size = second * len(CORNER_TYPES)
    w1 = conv_weights(first, channels, length)
    w2 = conv_weights(second, first, length)
    w3 = summary_size + 1
    expect(plan, name, f"{first} × {channels} × {length} + {first} = {w1}", "weight arithmetic")
    expect(plan, name, f"{second} × {first} × {length} + {second} = {w2}", "weight arithmetic")
    expect(plan, name, f"{summary_size} + 1 = {w3}", "weight arithmetic")
    expect(plan, name, f"**{w1 + w2 + w3}**", "weight arithmetic")
    expect(plan, name, f"the {w1 + w2 + w3}-weight model", "weight arithmetic")
    expect(plan, name, f"({', '.join(CORNER_TYPES)}): {summary_size} numbers", "identification.CORNER_TYPES")

    # The feature counts the baselines are named by.
    corner_count = len(ALL_FEATURES) * len(CORNER_TYPES)
    expect(plan, name, f"Corner features ({corner_count})", "identification.ALL_FEATURES")
    expect(plan, name, f"Whole-lap statistics ({len(RAW_STATS)})", "identification.RAW_STATS")
    expect(plan, name, f"Both together ({corner_count + len(RAW_STATS)})", "both")

    # The development pairs.
    pairs = pd.read_csv(RESULTS / "12_identification" / "teammates.csv")
    expect(plan, name, f"Development has {len(pairs)} team-seasons, with {pairs['laps'].min()}–{pairs['laps'].max()} "
                       f"laps and {pairs['sessions'].min()}–{pairs['sessions'].max()} weekends each", "teammates.csv")
    expect(plan, name, f"({pairs['laps'].min()}–{pairs['laps'].max()} laps per team-season)", "teammates.csv")

    # The baseline table: development and 2025.
    development = load("12_identification/summary.json")["teammates"]
    final = load("final/summary.json")["h3"]
    combined = load("32_combined_inputs/summary.json")["data"]
    both_dev = combined["development 2023-2024"]
    both_2025 = combined["2025 (second look)"]
    teams_2025 = final["ours minus lap time only"]["team_seasons"]
    expect(plan, name, f"Development 2023–2024 ({both_dev['team_seasons']} team-seasons) | 2025 ({teams_2025} teams)",
           "summaries")
    rows = [("Lap time only", "lap time only | balanced_accuracy", None),
            (f"Corner features ({corner_count})", "our features | balanced_accuracy", None),
            (f"Whole-lap statistics ({len(RAW_STATS)})", "raw lap statistics | balanced_accuracy", None),
            (f"Both together ({corner_count + len(RAW_STATS)})", None, "both")]
    for label, h3_key, combined_key in rows:
        if h3_key is not None:
            dev_value, value_2025 = development[h3_key]["mean"], final[h3_key]["mean"]
        else:
            dev_value = both_dev["mean_balanced_accuracy"][combined_key]
            value_2025 = both_2025["mean_balanced_accuracy"][combined_key]
        expect(plan, name, f"| {label} | {dev_value:.3f} | {value_2025:.3f} |", "summaries")
    # The combined-inputs check must agree with H3 where they overlap.
    assert abs(both_dev["mean_balanced_accuracy"]["corner features"]
               - development["our features | balanced_accuracy"]["mean"]) < 1e-9
    expect(plan, name, f"about {teams_2025} team pairs (2025 had {teams_2025})", "final summary")

    # The feed.
    rate = load("01_data_pilot/summary.json")["check_1_sample_timing"]["car"]["rate_from_mean_hz"]
    expect(plan, name, f"about {rate:.2f} samples per second, roughly one every {300 / 3.6 / rate:.0f} m at 300 km/h",
           "01_data_pilot")
    expect(plan, name, f"nothing faster than about {rate / 2:.1f} Hz", "01_data_pilot (Nyquist)")
    corners = pd.read_csv(RESULTS / "09_dataset" / "sessions.csv")
    with_corners = corners.loc[corners["corners"] > 0, "corners"]
    expect(plan, name, f"A 2023–2024 session has {int(with_corners.min())}–{int(with_corners.max())} braking zones",
           "09_dataset/sessions.csv")

    # Cross-references: the quoted phrases and every path the plan names.
    notes = text_of("docs/engineering_notes.md")
    expect(plan, name, "(up to 23 s, `docs/engineering_notes.md`)", "the plan")
    expect(notes, "engineering_notes.md", "holes of up to 23 s", "the plan's reference")
    expect(text_of("docs/decisions.md"), "decisions.md", "## 2026-11-13", "the plan's reference")
    expect(text_of("docs/decisions.md"), "decisions.md", "Instead of a neural network", "the plan's reference")
    from apextrace.data_loading import FROZEN_SEASONS
    assert {2025, 2026} <= set(FROZEN_SEASONS)
    for path in ["docs/decisions.md", "results/12_identification/summary.json", "results/final/summary.json",
                 "results/32_combined_inputs/summary.json", "docs/engineering_notes.md",
                 "src/apextrace/data_loading.py", "experiments/32_combined_inputs.py"]:
        assert f"`{path}`" in plan, path
        assert (REPO_ROOT / path).exists(), path
