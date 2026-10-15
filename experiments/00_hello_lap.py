"""Hello lap: load one real F1 session and plot one lap.

This is the finish line of Phase 0. If it runs, the environment, FastF1 and
the cache all work. It is also our first look at the data the project is
built on: Norris's pole lap at the 2024 Abu Dhabi GP qualifying.

Run from the repo root:
    .venv\\Scripts\\python.exe experiments\\00_hello_lap.py
Output:
    results/figures/00_hello_lap.png

What to look for in the plot:
  - over 300 km/h on the long straights, deep dips at the slow corners;
  - the dots. Each one is a real measurement. At ~3.7 Hz and 300 km/h they
    are ~22.5 m apart, so the line between two dots is only a straight-line
    guess (linear interpolation), not data.

The first run downloads the session into cache/ (takes a minute or so).
Later runs read from the cache and are much faster.
"""

from pathlib import Path

import fastf1
import matplotlib.pyplot as plt

from apextrace.plots import DRIVER_COLORS, TEXT_SECONDARY, apply_style

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "cache"
FIGURE_PATH = REPO_ROOT / "results" / "figures" / "00_hello_lap.png"


def main():
    # 1. Load the session (from the internet the first time, then from cache/)
    CACHE_DIR.mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))
    session = fastf1.get_session(2024, "Abu Dhabi", "Q")
    session.load()

    # 2. Pick Norris's fastest lap and get its car data (speed, throttle, ...)
    lap = session.laps.pick_drivers("NOR").pick_fastest()
    car = lap.get_car_data().add_distance()  # adds "Distance" in metres

    # 3. Print a few numbers to check by eye
    lap_seconds = lap["LapTime"].total_seconds()
    print(f"Lap time:        {lap['LapTime']}  ({lap_seconds:.3f} s)")
    print(f"Car-data rows:   {len(car)}")
    print(f"Average rate:    {len(car) / lap_seconds:.2f} samples per second")
    print(f"Lap distance:    {car['Distance'].iloc[-1]:.0f} m (from integrating speed)")
    print(f"Speed range:     {car['Speed'].min():.0f} to {car['Speed'].max():.0f} km/h")

    # 4. Plot speed against distance: the line, plus a dot per real sample
    apply_style()
    fig, ax = plt.subplots(figsize=(11, 4.2))
    color = DRIVER_COLORS["NOR"]
    ax.plot(car["Distance"], car["Speed"], color=color, linewidth=1.5)
    ax.plot(car["Distance"], car["Speed"], linestyle="none", marker="o",
            markersize=2.5, color=color)
    ax.set_title("Norris, fastest lap, 2024 Abu Dhabi GP qualifying", pad=20)
    ax.text(0.0, 1.01, f"{lap_seconds:.3f} s · each dot is one car-data sample "
            f"({len(car)} samples)", transform=ax.transAxes, fontsize=9,
            color=TEXT_SECONDARY, va="bottom")
    ax.set_xlabel("Distance along the lap (m)")
    ax.set_ylabel("Speed (km/h)")
    ax.set_xlim(0, car["Distance"].iloc[-1])

    FIGURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURE_PATH, bbox_inches="tight")
    print(f"Saved {FIGURE_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
