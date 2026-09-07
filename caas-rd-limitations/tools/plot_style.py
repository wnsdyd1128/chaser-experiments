"""Figure conventions shared by the exp5 plots.

Two things have to agree across the figures: how a number is set, and how the
two decisions are marked. A star sits over the placement the measurement picked
and an open diamond over the one CAAS predicted, so a misprediction reads as the
two marks standing over different bars, and agreement as the star sitting inside
the diamond. Both are drawn with the same Line2D
settings in the plot and in the legend, so the keys match what the bars carry.
"""

from __future__ import annotations

BEST_MARKER = {
    "marker": "o",
    "markersize": 6.0,
    "color": "0.1",
    "linestyle": "none",
}

PREDICTION_MARKER = {
    "marker": "o",
    "markersize": 11.0,
    "markerfacecolor": "none",
    "markeredgewidth": 1.3,
    "color": "0.1",
    "linestyle": "none",
}


def sci(value: float) -> str:
    """Scientific notation as mathtext, which is what a paper sets."""
    mantissa, exponent = f"{value:.2e}".split("e")
    return f"${mantissa}\\times10^{{{int(exponent)}}}$"


def decision_handles(best_label: str = "Measured best",
                     prediction_label: str = "CAAS prediction"):
    """Legend keys for the two marks, drawn exactly as the plot draws them."""
    from matplotlib.lines import Line2D

    return [Line2D([], [], label=best_label, **BEST_MARKER),
            Line2D([], [], label=prediction_label, **PREDICTION_MARKER)]
