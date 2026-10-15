"""One shared look for every figure in the project.

Why a module for this: if every experiment script picks its own colours and
fonts, Norris is blue in one figure and orange in the next, and a reader has
to re-learn every chart. Here colour follows the *entity* (a driver keeps
the same colour everywhere), axes and grid stay quiet so the data stands out,
and text is always grey/black ink, never the line colour.

The colours come from a palette checked for colour-blind readers: slot 1
(blue) and slot 2 (orange) stay distinguishable for the common types of
colour blindness.
"""

import matplotlib.pyplot as plt

# Chart surface and text "ink"
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"

# Categorical colours in a fixed order: the first entity always gets slot 1,
# the second slot 2, and so on. Never cycle or re-order them.
SERIES = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
]

# Fixed colour per driver, so a driver looks the same in every figure.
DRIVER_COLORS = {
    "NOR": SERIES[0],
    "PIA": SERIES[1],
}


def apply_style():
    """Set matplotlib defaults for all project figures. Call once per script."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "font.size": 10,
        "text.color": TEXT_PRIMARY,
        "axes.labelcolor": TEXT_SECONDARY,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.edgecolor": GRID,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT_SECONDARY,
        "lines.linewidth": 1.5,
        "legend.frameon": False,
    })
