"""Day 15: re-check and draw the frozen 2026 result (H5). Reads results only; runs no test again.

The preregistered decision is in results/final_2026/ (23_final_2026.py, run once on
2026-11-07, Part C + Addendum 1). Nothing here changes it. This script:

  1. RE-CHECKS the frozen numbers from the saved per-driver tables, with an independent
     implementation (SciPy's binomial test instead of our own sign test):
       - own_closer must equal "distance to own past < distance to teammate" on every row;
       - the count, the one-sided p-value and the exact 95 % interval must equal summary.json.
     Example: 13 of 19 -> P(13 or more of 19 heads) = 0.0835, interval 0.43-0.87.
  2. Draws one figure for the report: per driver, how much closer the 2026 signature is to
     their own 2025 signature than to their 2025 teammate's, next to the same share in the two
     development pairs of seasons (no rule change).
  3. Counts, as an EXPLORATORY description (not preregistered, no decision), how the pairs of
     2025 teammates who were both compared came out: both "own past", both "teammate", or split
     one-and-one. A car-only effect makes pairs split (71 % in the synthetic null check,
     experiment 22), which is why the sign test is conservative here.

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\27_final_2026_figures.py
"""

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch
from scipy.stats import binomtest

from apextrace.plots import GRID, SERIES, TEXT_SECONDARY, apply_style
from apextrace.signatures import sign_test_threshold

REPO_ROOT = Path(__file__).resolve().parent.parent
FINAL_DIR = REPO_ROOT / "results" / "final_2026"
DEVELOPMENT = REPO_ROOT / "results" / "20_h5_development" / "summary.json"
OUT_DIR = REPO_ROOT / "results" / "27_final_2026_figures"

# feature set name in summary.json -> its per-driver file
SET_FILES = {"all": "h5_all.csv", "control points": "h5_control_points.csv",
             "energy-sensitive": "h5_energy-sensitive.csv", "no throttle": "h5_no_throttle.csv"}


def recheck(table, frozen, distance_own, distance_other):
    """Recompute one frozen sign-test block from its per-driver table; return a list of problems.

    The per-driver table stores both distances and the yes/no answer. If the answer column,
    the count, the p-value or the interval in summary.json disagreed with what the distances
    give, the frozen summary would not describe the frozen data. SciPy's binomtest is an
    independent implementation of the same exact test.
    Example (H5 primary): 13 rows with distance_own < distance_teammate out of 19 ->
    binomtest(13, 19, 0.5, "greater").pvalue = 0.0835 = summary.json's sign_test_p.
    """
    problems = []
    rows = table[table["included"] == True]  # noqa: E712 (a column of True/False)
    for row in rows.itertuples():
        closer = getattr(row, distance_own) < getattr(row, distance_other)
        if bool(closer) != bool(row.own_closer):
            problems.append(f"{row.driver}: own_closer does not match the two distances")
    successes, trials = int(rows["own_closer"].sum()), int(len(rows))
    if successes != frozen["own_closer"] or trials != frozen["drivers"]:
        problems.append(f"count {successes} of {trials} differs from summary.json")
    if trials > 0:
        result = binomtest(successes, trials, 0.5, alternative="greater")
        # the interval must come from a TWO-sided test object: SciPy's proportion_ci follows the
        # test's alternative, and a "greater" test gives a one-sided interval (low, 1.0)
        two_sided = binomtest(successes, trials, 0.5, alternative="two-sided")
        interval = two_sided.proportion_ci(confidence_level=0.95, method="exact")
        if not math.isclose(result.pvalue, frozen["sign_test_p"], rel_tol=1e-9):
            problems.append(f"p {result.pvalue} differs from summary.json {frozen['sign_test_p']}")
        if not (math.isclose(interval.low, frozen["ci95_low"], abs_tol=1e-6)
                and math.isclose(interval.high, frozen["ci95_high"], abs_tol=1e-6)):
            problems.append("exact 95 % interval differs from summary.json")
    return problems


def teammate_pairs(table):
    """EXPLORATORY: pairs of 2025 teammates who were both compared -> how each pair came out.

    Each driver's row names their 2025 teammate. A pair counts once, and only when both
    drivers are included. Example: NOR (own closer) and PIA (own closer) -> "both own past";
    ALB (teammate closer) and SAI (own closer) -> "split".
    """
    included = table[table["included"] == True].set_index("driver")  # noqa: E712
    seen = set()
    pairs = []
    for driver, row in included.iterrows():
        mate = row["teammate"]
        key = tuple(sorted([driver, mate]))
        if mate not in included.index or key in seen:
            continue
        seen.add(key)
        own_count = int(bool(row["own_closer"])) + int(bool(included.loc[mate, "own_closer"]))
        outcome = {2: "both own past", 1: "split", 0: "both teammate"}[own_count]
        pairs.append({"pair": f"{key[0]}/{key[1]}", "outcome": outcome})
    return pd.DataFrame(pairs)


def figure(h5_table, points, needed_share):
    """Left: per driver, (distance to 2025 teammate) - (distance to own 2025); positive = own
    past closer. Right: the share of drivers closer to their own past, with exact 95 %
    intervals, in the two development pairs of seasons and in the frozen 2026 test."""
    rows = h5_table[h5_table["included"] == True].copy()  # noqa: E712
    rows["margin"] = rows["distance_teammate"] - rows["distance_own"]
    rows = rows.sort_values("margin")
    labels = []
    for driver, team_before, team_after in zip(rows["driver"], rows["team_reference"], rows["team_target"]):
        renamed_only = {team_before, team_after} == {"Kick Sauber", "Audi"}    # same team lineage
        labels.append(driver if team_before == team_after or renamed_only else f"{driver} (new team)")

    fig, (left, right) = plt.subplots(1, 2, figsize=(10.5, 5.6), gridspec_kw={"width_ratios": [1.35, 1]})
    colors = [SERIES[0] if margin > 0 else SERIES[1] for margin in rows["margin"]]
    left.barh(range(len(rows)), rows["margin"], height=0.62, color=colors)
    left.axvline(0, color=TEXT_SECONDARY, linewidth=1)
    left.set_yticks(range(len(rows)))
    left.set_yticklabels(labels, fontsize=8)
    left.set_xlabel("distance to 2025 teammate − distance to own 2025\n(right of 0: own past closer)", fontsize=8)
    own = int((rows["margin"] > 0).sum())
    left.set_title(f"2026 vs 2025, per driver: {own} of {len(rows)} closer to their own past", fontsize=9, pad=8)
    left.grid(axis="y", visible=False)          # a grid line at each tick would cut through the bars
    left.set_axisbelow(True)
    handles = [Patch(color=SERIES[0], label="own 2025 signature closer"),
               Patch(color=SERIES[1], label="2025 teammate's closer")]
    left.legend(handles=handles, loc="lower right", fontsize=8, frameon=False)

    for k, point in enumerate(points):
        right.errorbar([k], [point["share"]], yerr=[[point["share"] - point["low"]], [point["high"] - point["share"]]],
                       fmt="o", color=SERIES[0], markersize=8, capsize=4, linewidth=1.5)
        right.annotate(point["count"], (k, point["share"]), xytext=(9, -3), textcoords="offset points",
                       fontsize=8, color=TEXT_SECONDARY)
    right.axhline(0.5, color=TEXT_SECONDARY, linewidth=1, linestyle="--")
    right.text(-0.4, 0.51, "chance (coin flip)", fontsize=8, color=TEXT_SECONDARY)
    last = len(points) - 1
    # drawn in ink, not in a series colour: orange already means "teammate closer" on the left
    right.plot([last - 0.25, last + 0.25], [needed_share, needed_share], color=TEXT_SECONDARY, linewidth=2)
    right.annotate("needed for p < 0.05", (last - 0.25, needed_share), xytext=(-4, 0), textcoords="offset points",
                   fontsize=8, color=TEXT_SECONDARY, ha="right", va="center")
    right.set_xticks(range(len(points)))
    right.set_xticklabels([point["label"] for point in points], fontsize=8)
    right.set_xlim(-0.5, last + 0.5)
    right.set_ylim(0.3, 1.0)
    right.set_ylabel("share of drivers closer to their own past (exact 95 % interval)", fontsize=8)
    right.set_title("same comparison, with and without a rule change", fontsize=9, pad=8)
    right.grid(axis="x", visible=False)
    right.grid(axis="y", color=GRID)
    fig.suptitle("2026 (frozen test, H5): does the signature survive the rule change?", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "final_h5.png", bbox_inches="tight", dpi=150)
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    with open(FINAL_DIR / "summary.json", encoding="utf-8") as file:
        frozen = json.load(file)
    with open(DEVELOPMENT, encoding="utf-8") as file:
        development = json.load(file)["pairs"]

    # 1. re-check every frozen block from its per-driver table
    problems = {}
    for name, filename in SET_FILES.items():
        table = pd.read_csv(FINAL_DIR / filename)
        problems[f"h5 {name}"] = recheck(table, frozen["h5"]["sets"][name], "distance_own", "distance_teammate")
    for group in ("changers", "stayers"):
        table = pd.read_csv(FINAL_DIR / f"h4_{group}.csv")
        problems[f"h4 {group}"] = recheck(table, frozen["h4"][group], "distance_own_reference", "distance_new_teammate")
    for block, found in problems.items():
        print(f"{block:24s} {'matches summary.json' if not found else found}")
    all_match = all(len(found) == 0 for found in problems.values())
    assert all_match, "a frozen number does not match its own per-driver table"

    # 2. the figure
    h5_table = pd.read_csv(FINAL_DIR / "h5_all.csv")
    points = []
    for label, key in (("2023 → 2024\n(development)", "2023 -> 2024"), ("2024 → 2025\n(development)", "2024 -> 2025")):
        block = development[key]["all"]
        points.append({"label": label, "share": block["share"], "low": block["ci95_low"], "high": block["ci95_high"],
                       "count": f"{block['own_closer']} of {block['drivers']}"})
    primary = frozen["h5"]["sets"]["all"]
    points.append({"label": "2025 → 2026\n(frozen test, new rules)", "share": primary["share"],
                   "low": primary["ci95_low"], "high": primary["ci95_high"],
                   "count": f"{primary['own_closer']} of {primary['drivers']}"})
    needed = sign_test_threshold(primary["drivers"])
    figure(h5_table, points, needed / primary["drivers"])

    # 3. exploratory: how the pairs of 2025 teammates came out
    pairs = teammate_pairs(h5_table)
    pairs.to_csv(OUT_DIR / "teammate_pairs.csv", index=False)
    print(pairs.to_string(index=False))
    outcomes = pairs["outcome"].value_counts()

    summary = {
        "note": "re-check + figure + EXPLORATORY pair counts; the preregistered decision is results/final_2026/",
        "recomputed_from_tables": {block: (found if found else "matches") for block, found in problems.items()},
        "all_match": all_match,
        "needed_of_drivers": {"needed": needed, "drivers": primary["drivers"]},
        "exploratory_teammate_pairs": {"pairs": int(len(pairs)), "split": int(outcomes.get("split", 0)),
                                       "both_own_past": int(outcomes.get("both own past", 0)),
                                       "both_teammate": int(outcomes.get("both teammate", 0)),
                                       "drivers_without_their_teammate": int(primary["drivers"] - 2 * len(pairs))},
    }
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)
    print(json.dumps(summary["exploratory_teammate_pairs"]))
    print(f"wrote {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
