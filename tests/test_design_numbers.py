"""docs/h5_design.md is written by hand (it becomes preregistration Part C), so its numbers
could be mistyped or go stale. This test rebuilds every quoted number from the committed
results files (or recomputes it with the project's own functions) and checks that the exact
phrase is in the file. README.md and docs/report.md are generated instead (test_docs.py).

If a result changes, this test fails until the design file is updated: that's the point.
It reads only committed result files; no F1 data is downloaded.
"""

import json
from pathlib import Path

import pytest

from apextrace.signatures import sign_test_power, sign_test_threshold

REPO_ROOT = Path(__file__).resolve().parent.parent
DESIGN = REPO_ROOT / "docs" / "h5_design.md"
RESULTS = REPO_ROOT / "results"


def load(relative):
    return json.loads((RESULTS / relative).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def design():
    return DESIGN.read_text(encoding="utf-8")


def expect(design, phrase, source):
    assert phrase in design, f"docs/h5_design.md should contain {phrase!r} (from {source})"


def test_development_baselines_and_variants(design):
    pairs = load("20_h5_development/summary.json")["pairs"]
    for label, result in pairs.items():
        overall = result["all"]
        expect(design, f"{overall['own_closer']} of {overall['drivers']}", f"20_h5_development, {label}")
        expect(design, f"{overall['ci95_low']:.2f}–{overall['ci95_high']:.2f}", f"20_h5_development, {label} interval")
        expect(design, f"({overall['share']:.2f}", f"20_h5_development, {label} share")
        for name, variant in result["variants"].items():
            expect(design, f"{variant['own_closer']} of {variant['drivers']} ({variant['share']:.2f})",
                   f"20_h5_development, {label}, {name}")
        full = result["full_season_references"]
        expect(design, f"{full['own_closer']} of {full['drivers']}", f"20_h5_development, {label}, full-season")
    changers = pairs["2024 -> 2025"]
    expect(design, f"{changers['changers_own_closer']} of {len(changers['changers'])} changers",
           "20_h5_development, 2024 -> 2025 changers")


def test_power_table_rows(design):
    """Each row: n, successes needed, power at q = 0.6 ... 0.9, recomputed with the code."""
    for drivers in (14, 16, 18, 20):
        cells = [str(drivers), str(sign_test_threshold(drivers))]
        for q in (0.6, 0.7, 0.8, 0.85, 0.9):
            cells.append(f"{sign_test_power(drivers, q):.2f}")
        expect(design, "| " + " | ".join(cells) + " |", "signatures.sign_test_power")


def test_power_at_the_measured_baselines(design):
    pairs = load("20_h5_development/summary.json")["pairs"]
    first = list(pairs["2023 -> 2024"]["power_if_2026_had_this_rate"].values())
    expect(design, f"{round(min(first) * 100)}–{round(max(first) * 100)} %", "20_h5_development power, 2023 -> 2024")
    second = list(pairs["2024 -> 2025"]["power_if_2026_had_this_rate"].values())
    if min(second) >= 0.99:
        expect(design, "99 % or more", "20_h5_development power, 2024 -> 2025")
    else:
        expect(design, f"{round(min(second) * 100)}–{round(max(second) * 100)} %", "20_h5_development power, 2024 -> 2025")


def test_eligible_drivers_and_no_rule_change_power_inputs(design):
    power = load("19_h5_power/summary.json")
    expect(design, f"**{power['eligible_upper_bound']}**", "19_h5_power eligible upper bound")


def test_null_check_numbers(design):
    cases = load("22_h5_null_check/summary.json")["cases"]
    expect(design, f"{cases['B pair inside the spread']['share']:.2f} \"own closer\"", "22_h5_null_check B")
    expect(design, f"gave {cases['C H5 rules, few-weekends teammate']['share']:.2f}", "22_h5_null_check C")
    expect(design, f"full-season teammates {cases['D H5 rules, full-season teammates']['share']:.2f}",
           "22_h5_null_check D")


def test_coasting_check_numbers(design):
    coasting = load("21_coasting_check/summary.json")
    expect(design, f"worst case {coasting['worst']['rmse_m']:.2f} m", "21_coasting_check worst")
    expect(design, f"{coasting['threshold_m']} m", "21_coasting_check threshold")
    assert coasting["consequence_add_variant_without_braking_features"] is False
    expect(design, "so nothing changes", "21_coasting_check consequence")


def allowed_counts_and_intervals():
    """Every "k of n" and every "low–high" interval the design file may quote, built from
    the results files. Anything else in the file is a typo or a stale number."""
    counts, intervals = set(), set()
    development = load("20_h5_development/summary.json")["pairs"]
    for result in development.values():
        for block in [result["all"], result["stayed"], result["full_season_references"], *result["variants"].values()]:
            counts.add(f"{block['own_closer']} of {block['drivers']}")
        counts.add(f"{result['changers_own_closer']} of {len(result['changers'])}")
        intervals.add(f"{result['all']['ci95_low']:.2f}–{result['all']['ci95_high']:.2f}")
    baselines = load("19_h5_power/summary.json")["baselines"]
    for baseline in baselines:
        counts.add(f"{baseline['successes']} of {baseline['trials']}")
    shares = [baseline["share"] for baseline in baselines]
    intervals.add(f"{min(shares):.2f}–{max(shares):.2f}")
    frozen_h4 = load("final/summary.json")["h4"]
    counts.add(f"{frozen_h4['own_closer']} of {frozen_h4['changers_included']}")
    control = load("15_final_exploratory/summary.json")["changers_vs_stayers"]
    counts.add(control["stayers_own_closer"])
    setup = load("22_h5_null_check/summary.json")["setup"]
    counts.add(f"{setup['teammate_weekends']} of {setup['weekends']}")
    return counts, intervals


def test_every_count_and_interval_in_the_file_comes_from_a_result(design):
    """Catches a mistyped copy of a number that is quoted more than once (a simple
    "is the right phrase somewhere?" check would still find the correct copy)."""
    import re

    counts, intervals = allowed_counts_and_intervals()
    for phrase in re.findall(r"\b\d+ of \d+\b", design):
        assert phrase in counts, f"docs/h5_design.md quotes {phrase!r}, which no results file gives"
    for phrase in re.findall(r"\d\.\d{2}–\d\.\d{2}", design):
        assert phrase in intervals, f"docs/h5_design.md quotes the interval {phrase!r}, which no results file gives"
