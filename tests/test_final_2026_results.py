"""The frozen 2026 numbers (results/final_2026/summary.json) must agree with their own per-driver tables.

The one-time 2026 test can never be re-run, so its summary can't be checked by running it
again. What CAN be checked, on every push, is that the summary describes the saved tables:
each own_closer answer follows from its two distances, and each count, one-sided p-value and
exact interval matches SciPy's binomial test (an independent implementation). The check
itself is experiments/27_final_2026_figures.py's `recheck`. Reads committed files only.
"""

import importlib.util
import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
FINAL_DIR = REPO_ROOT / "results" / "final_2026"


def load_experiment_27():
    spec = importlib.util.spec_from_file_location("figures_2026", REPO_ROOT / "experiments" / "27_final_2026_figures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_summary():
    with open(FINAL_DIR / "summary.json", encoding="utf-8") as file:
        return json.load(file)


def test_every_frozen_block_matches_its_per_driver_table():
    experiment = load_experiment_27()
    summary = frozen_summary()
    for name, filename in experiment.SET_FILES.items():
        table = pd.read_csv(FINAL_DIR / filename)
        assert experiment.recheck(table, summary["h5"]["sets"][name], "distance_own", "distance_teammate") == [], name
    for group in ("changers", "stayers"):
        table = pd.read_csv(FINAL_DIR / f"h4_{group}.csv")
        assert experiment.recheck(table, summary["h4"][group], "distance_own_reference", "distance_new_teammate") == []


def test_the_recheck_catches_a_wrong_count_p_value_interval_or_answer():
    """The check must fail on each kind of disagreement, or it proves nothing."""
    experiment = load_experiment_27()
    frozen = frozen_summary()["h5"]["sets"]["all"]
    table = pd.read_csv(FINAL_DIR / "h5_all.csv")
    for key, wrong in (("own_closer", frozen["own_closer"] + 1), ("sign_test_p", 0.05), ("ci95_low", 0.45)):
        changed = dict(frozen)
        changed[key] = wrong
        assert experiment.recheck(table, changed, "distance_own", "distance_teammate") != [], key
    # swap one driver's two distances: the stored answer no longer follows from them, whichever
    # way it went (a first version only made the own distance larger, which left ALB's "no" valid)
    flipped = table.copy()
    flipped.loc[0, ["distance_own", "distance_teammate"]] = [table.loc[0, "distance_teammate"],
                                                             table.loc[0, "distance_own"]]
    assert experiment.recheck(flipped, frozen, "distance_own", "distance_teammate") != []


def test_the_verdict_follows_the_preregistered_rule():
    """Part C: H5 is supported if the one-sided sign test on the primary set gives p < 0.05."""
    from apextrace.signatures import sign_test_threshold

    summary = frozen_summary()
    primary = summary["h5"]["sets"]["all"]
    supported = primary["own_closer"] >= sign_test_threshold(primary["drivers"])
    assert supported == (primary["sign_test_p"] < 0.05) == summary["h5"]["supported"]
    assert summary["h5"]["verdict"] == ("supported" if supported else "not supported")
