"""Phase 7, H4 development on 2023 -> 2024: does a driver's season signature follow the DRIVER?

Nobody (among the regulars) changed teams between 2023 and 2024, so the real
team-change test has to wait for 2025 (frozen). This develops and checks the
method on what we have:

  1. Own-rank: for each driver racing both seasons, rank all 2023 signatures by
     distance from the driver's 2024 signature. Rank 1 = their own 2023
     signature is the closest. Chance: mean rank (N + 1) / 2. Permutation test:
     shuffle which 2023 signature belongs to whom (10,000 times).
     Note: driver AND car were the same in both years, so this measures
     driver + car stability, not the driver alone.
  2. Own vs teammate (the H4 analogue): is a driver's 2024 signature closer to
     their own 2023 signature than to their 2023 TEAMMATE's (same car)? If the
     signature were only the car, own and teammate would be equally close
     (a coin flip per driver). One-sided sign test.
  3. The same two checks for the brake-flag share (the strongest raw
     statistic in H3), to see whether it is stable for a driver.

Signatures: season means of the lap vectors (30 field-relative corner
features), each weekend counted once, drivers with >= 5 weekends a season,
z-scored with the 2023 spread (signatures.standardise).

Outputs in results/13_signature_stability/. Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\13_signature_stability.py
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apextrace.dataset import add_field_relative, clean, load_dataset
from apextrace.identification import build_lap_table
from apextrace.plots import SERIES, TEXT_SECONDARY, apply_style
from apextrace.signatures import distance_table, own_rank, season_signatures, sign_test_p, standardise

REPO_ROOT = Path(__file__).resolve().parent.parent
RAW = REPO_ROOT / "results" / "09_dataset" / "raw_samples.parquet"
OUT_DIR = REPO_ROOT / "results" / "13_signature_stability"
OLD, NEW = 2023, 2024
PERMUTATIONS = 10000
SEED = 2026
# Teams renamed between seasons are the same team (same car lineage)
SAME_TEAM_AS = {"AlphaTauri": "RB", "Alfa Romeo": "Kick Sauber"}


def lineage(team):
    return SAME_TEAM_AS.get(team, team)


def load_laps():
    data, _ = clean(load_dataset())
    raw = pd.read_parquet(RAW, columns=["session_key", "driver", "lap", "speed_kmh", "throttle_pct", "brake"])
    return build_lap_table(add_field_relative(data), raw)


def own_rank_test(distances, drivers, rng):
    """Observed mean own-rank, and how often shuffled identities give a mean rank at least as good."""
    observed = [own_rank(distances, d) for d in drivers]
    reference_names = list(distances.columns)
    better = 0
    for _ in range(PERMUTATIONS):
        shuffled = distances.copy()
        shuffled.columns = rng.permutation(reference_names)
        ranks = [own_rank(shuffled, d) for d in drivers]
        if np.mean(ranks) <= np.mean(observed):
            better += 1
    return observed, (better + 1) / (PERMUTATIONS + 1)


def teammate_comparison(distances, signatures_old, signatures_new, drivers):
    rows = []
    for driver in drivers:
        team = lineage(signatures_new.loc[driver, "team"])
        mates = [d for d in signatures_old.index if d != driver and lineage(signatures_old.loc[d, "team"]) == team]
        if not mates:
            continue
        mate_distance = float(np.mean([distances.loc[driver, m] for m in mates]))
        rows.append({"driver": driver, "team": team, "old_teammates": " ".join(mates),
                     "distance_own": float(distances.loc[driver, driver]), "distance_teammate": mate_distance,
                     "own_closer": bool(distances.loc[driver, driver] < mate_distance)})
    return pd.DataFrame(rows)


def figure(distances, drivers):
    matrix = distances.loc[drivers, drivers].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(8.5, 7.5))
    image = ax.imshow(matrix, cmap="Blues_r")
    ax.set_xticks(range(len(drivers)))
    ax.set_xticklabels(drivers, rotation=90, fontsize=8)
    ax.set_yticks(range(len(drivers)))
    ax.set_yticklabels(drivers, fontsize=8)
    ax.grid(False)
    for i in range(len(drivers)):
        ax.add_patch(plt.Rectangle((i - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=SERIES[1], linewidth=1.5))
    ax.set_xlabel(f"{OLD} signature of")
    ax.set_ylabel(f"{NEW} signature of")
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label="distance (dark = similar)")
    ax.set_title(f"Season signatures {NEW} vs {OLD} (orange: same driver)", fontsize=10, pad=10)
    fig.savefig(OUT_DIR / "signature_distances.png", bbox_inches="tight")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_style()
    rng = np.random.default_rng(SEED)
    laps = load_laps()
    corner_columns = [c for c in laps.columns if "__" in c]
    signatures = season_signatures(laps, corner_columns + ["share_braking_rel"])
    old_raw = signatures.xs(OLD, level="year")
    new_raw = signatures.xs(NEW, level="year")
    drivers = sorted(set(old_raw.index) & set(new_raw.index))
    old = standardise(old_raw, corner_columns, old_raw)
    new = standardise(new_raw, corner_columns, old_raw)

    summary = {"drivers_in_both_seasons": len(drivers), "drivers": drivers}
    print(f"{len(drivers)} drivers with >= 5 weekends in both {OLD} and {NEW}: {' '.join(drivers)}")

    # 1-2: corner-feature signatures
    distances = distance_table(new.loc[drivers], old, corner_columns)
    distances.to_csv(OUT_DIR / "distances_corner_features.csv", float_format="%.4f")
    ranks, p_rank = own_rank_test(distances, drivers, rng)
    mates = teammate_comparison(distances, old_raw, new_raw, drivers)
    mates.to_csv(OUT_DIR / "own_vs_teammate_corner_features.csv", index=False, float_format="%.4f")
    wins = int(mates["own_closer"].sum())
    summary["corner_features"] = {
        "own_ranks": dict(zip(drivers, ranks)), "mean_own_rank": float(np.mean(ranks)),
        "chance_mean_rank": (len(old) + 1) / 2, "rank_1_count": int(sum(r == 1 for r in ranks)),
        "permutation_p": p_rank, "own_closer_than_teammate": wins, "pairs": int(len(mates)),
        "sign_test_p": sign_test_p(wins, len(mates))}
    s = summary["corner_features"]
    print(f"\ncorner features: mean own rank {s['mean_own_rank']:.2f} of {len(old)} (chance {s['chance_mean_rank']:.1f}), "
          f"rank 1 for {s['rank_1_count']} of {len(drivers)} drivers, permutation p = {p_rank:.4f}")
    print(f"own closer than the 2023 teammate (same car): {wins} of {len(mates)}, sign test p = {s['sign_test_p']:.4f}")
    print(mates.round(3).to_string(index=False))

    # 3: brake-flag share alone (one number per driver-season)
    share_old = old_raw["share_braking_rel"]
    share_new = new_raw.loc[drivers, "share_braking_rel"]
    correlation = float(np.corrcoef(share_old.loc[drivers], share_new)[0, 1])
    share_rows = []
    for driver in drivers:
        team = lineage(new_raw.loc[driver, "team"])
        mate_values = [share_old.loc[m] for m in old_raw.index if m != driver and lineage(old_raw.loc[m, "team"]) == team]
        if not mate_values:
            continue
        own_gap = abs(share_new.loc[driver] - share_old.loc[driver])
        mate_gap = abs(share_new.loc[driver] - float(np.mean(mate_values)))
        share_rows.append({"driver": driver, "own_closer": bool(own_gap < mate_gap)})
    share_table = pd.DataFrame(share_rows)
    share_wins = int(share_table["own_closer"].sum())
    summary["share_braking"] = {"correlation_old_new": correlation, "own_closer_than_teammate": share_wins,
                                "pairs": int(len(share_table)), "sign_test_p": sign_test_p(share_wins, len(share_table))}
    print(f"\nbrake-flag share: correlation {OLD} vs {NEW} across drivers {correlation:+.2f}; own closer than "
          f"teammate {share_wins} of {len(share_table)}, sign test p = {summary['share_braking']['sign_test_p']:.4f}")

    figure(distances, drivers)
    with open(OUT_DIR / "summary.json", "w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2, default=float)
    print(f"Saved results to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
