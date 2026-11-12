"""experiments/32_combined_inputs.py on known truths (synthetic laps, no F1 data).

The question it answers: do corner features add anything on top of whole-lap statistics? Two
synthetic worlds where the answer is known:
  - different information: both inputs carry the driver, each with its OWN noise, so together
    they must identify the driver better than either alone;
  - the same information: the corner input only repeats the informative whole-lap column, so
    together they can't do better than the whole-lap statistics alone.
"""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from apextrace.identification import RAW_STATS

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_script():
    spec = importlib.util.spec_from_file_location("combined", REPO_ROOT / "experiments" / "32_combined_inputs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_laps(rng, same_information, signal=1.0, teams=4, weekends=10, laps=8, corner_columns=10):
    """Two drivers per team. One whole-lap statistic is shifted by +-signal/2 for the two drivers.
    Corner column 0 is either shifted the same way with its own noise (different information) or an
    exact copy of that whole-lap statistic (the same information); the other corner columns are noise."""
    rows = []
    for team in range(teams):
        for weekend in range(weekends):
            for driver, sign in (("A", 0.5), ("B", -0.5)):
                for lap in range(laps):
                    row = {"team_season": f"T{team} 2024", "session_key": team * 100 + weekend,
                           "driver": f"{driver}{team}", "lap": lap}
                    for stat in RAW_STATS:
                        row[f"{stat}_rel"] = rng.normal()
                    row[f"{RAW_STATS[0]}_rel"] += sign * signal
                    for k in range(corner_columns):
                        row[f"f{k}_rel__slow"] = rng.normal()
                    if same_information:
                        row["f0_rel__slow"] = row[f"{RAW_STATS[0]}_rel"]
                    else:
                        row["f0_rel__slow"] += sign * signal
                    rows.append(row)
    return pd.DataFrame(rows)


def test_different_information_adds_up():
    script = load_script()
    table = script.compare_inputs(synthetic_laps(np.random.default_rng(1), same_information=False))
    assert len(table) == 4
    gain = (table["both"] - table["whole-lap statistics"]).mean()
    assert gain > 0.03, gain                     # two independent signals beat one


def test_the_same_information_adds_nothing():
    script = load_script()
    table = script.compare_inputs(synthetic_laps(np.random.default_rng(2), same_information=True))
    gain = (table["both"] - table["whole-lap statistics"]).mean()
    assert gain < 0.01, gain                     # a copy can't help (extra noise columns may even hurt)


def test_the_words_follow_the_interval():
    script = load_script()
    rng = np.random.default_rng(3)
    up = pd.DataFrame({"both": [0.80, 0.82, 0.79, 0.81, 0.83], "whole-lap statistics": [0.70, 0.71, 0.70, 0.72, 0.70]})
    flat = pd.DataFrame({"both": [0.70, 0.74, 0.69, 0.73, 0.71], "whole-lap statistics": [0.72, 0.71, 0.71, 0.72, 0.72]})
    assert script.difference_summary(up, "both", "whole-lap statistics", rng)["words"].endswith("beyond whole-lap statistics")
    assert script.difference_summary(flat, "both", "whole-lap statistics", rng)["words"].startswith("no clear gain")
