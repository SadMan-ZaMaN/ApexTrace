"""Which team is which across seasons, so team changers come from the data, not a hand-typed list.

Why this module exists: in the 2025 test, the team changers were typed in by hand and one
(Colapinto) was missed (docs/preregistration_deviations.md). From 2026 on, a driver is a
team changer if the team they drove for on most weekends belongs to a different LINEAGE
(the same entry and car line, whatever its name) in the two seasons.

Team names change with owners and sponsors ("AlphaTauri" -> "RB" -> "Racing Bulls"), so a
name is matched by keywords. The map was fixed before any 2026 data was loaded. Entrants
announced before the 2026 season: Audi takes over the Sauber entry, and Cadillac is a new
team. A name that matches no keyword is NOT guessed: `lineage` raises an error, and the
one-time 2026 script stops before any result.
"""

import re

# (pattern, lineage). A name must match exactly ONE lineage: none -> unknown, two or more ->
# ambiguous (e.g. a constructor-style "McLaren Mercedes" matches McLaren and Mercedes), and both stop
# the 2026 script. "red bull racing" and the Racing Bulls patterns never match the same name.
LINEAGE_PATTERNS = [
    (r"red bull racing", "Red Bull Racing"),
    (r"racing bulls|alphatauri|toro rosso|^rb$|\brb f1\b", "Racing Bulls"),
    (r"sauber|alfa romeo|\baudi\b", "Sauber / Audi"),
    (r"\bhaas\b", "Haas"),
    (r"ferrari", "Ferrari"),
    (r"mercedes", "Mercedes"),
    (r"mclaren", "McLaren"),
    (r"aston martin", "Aston Martin"),
    (r"alpine", "Alpine"),
    (r"williams", "Williams"),
    (r"cadillac", "Cadillac"),
]


def lineage(team_name):
    """The lineage of a team name; ValueError if no lineage or more than one matches, or if
    the name is missing.

    Examples: "AlphaTauri", "RB" and "Racing Bulls" -> "Racing Bulls";
    "Alfa Romeo", "Kick Sauber" and "Audi" -> "Sauber / Audi";
    "Oracle Red Bull Racing" -> "Red Bull Racing" (sponsor names don't matter);
    "McLaren Mercedes" -> ValueError (McLaren or Mercedes? the code doesn't guess).
    """
    if team_name is None or (isinstance(team_name, float) and team_name != team_name) or not str(team_name).strip():
        raise ValueError("missing team name")
    name = str(team_name).strip().lower()
    matches = set()
    for pattern, team_lineage in LINEAGE_PATTERNS:
        if re.search(pattern, name):
            matches.add(team_lineage)
    if len(matches) == 1:
        return matches.pop()
    if not matches:
        raise ValueError(f"unknown team name {team_name!r}: add it to teams.LINEAGE_PATTERNS (and log why)")
    raise ValueError(f"ambiguous team name {team_name!r}: matches {sorted(matches)}")


def unknown_team_names(team_names):
    """The names `lineage` can't place: unknown, ambiguous, or missing (shown as "<missing>").
    Empty list = all known. The 2026 script checks this before building anything."""
    unknown = set()
    for name in team_names:
        try:
            lineage(name)
        except ValueError:
            unknown.add("<missing>" if name is None or str(name).strip() in ("", "nan") else str(name))
    return sorted(unknown)


def team_changers(laps, reference_year, target_year, min_sessions=5):
    """Drivers whose most-driven team in the target year is a different lineage from
    their most-driven team in the reference year. One row per driver in both years.

    "Most-driven" = most weekends (sessions); a mid-season swap after two rounds
    doesn't make a driver a changer for the team they left. Example: 2024 Mercedes
    -> 2025 Ferrari is a change; 2024 "RB" -> 2025 "Racing Bulls" is not.
    `eligible` = at least min_sessions weekends in BOTH years (the H4 rule). Below that a
    tie can decide the "most-driven" team: Bearman's dry 2024 = 1 Ferrari + 1 Haas weekend,
    so he would be a "changer" only by alphabetical order; he is not eligible.
    """
    import pandas as pd

    rows = []
    in_both = set(laps.loc[laps["year"] == reference_year, "driver"]) & set(laps.loc[laps["year"] == target_year, "driver"])
    for driver in sorted(in_both):
        teams, weekends = {}, {}
        for year in (reference_year, target_year):
            own = laps[(laps["year"] == year) & (laps["driver"] == driver)]
            per_team = own.groupby("team")["session_key"].nunique()
            teams[year] = per_team.idxmax()
            weekends[year] = int(own["session_key"].nunique())
        rows.append({"driver": driver, "team_reference": teams[reference_year], "team_target": teams[target_year],
                     "weekends_reference": weekends[reference_year], "weekends_target": weekends[target_year],
                     "eligible": min(weekends.values()) >= min_sessions,
                     "changed": lineage(teams[reference_year]) != lineage(teams[target_year])})
    return pd.DataFrame(rows)
