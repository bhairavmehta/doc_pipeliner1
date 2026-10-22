"""
Figure style reference for the pipeline.

Codex copies this style when it writes stories/<id>/figures.py: rounded boxes with centred text,
arrows between them, a small fixed colour palette and the Calibri font.
Run it to see the sample:  python figure_style.py   (writes figure_style_sample.png)
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

plt.rcParams["font.family"] = ["Calibri", "Carlito", "DejaVu Sans"]

# Palette (matches the Word document styling)
NAVY = "#1F3864"     # main boxes, headings
BLUE = "#2F5496"     # secondary
BLUE2 = "#4472C4"    # tier / highlight
LIGHT = "#D9E2F3"    # inputs, light boxes
GREY = "#595959"     # text, arrows
SAND = "#FBE5D6"     # examples, notes
AMBER = "#C55A11"    # feedback loops, warnings
GREEN = "#E2EFDA"    # outputs
GREEN_D = "#375623"


def box(ax, x, y, w, h, text, fc, ec, tc="black", size=9, bold=False, ls="-"):
    """Rounded box with centred text. Use \\n in text to wrap lines."""
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=fc, ec=ec, lw=1.2, linestyle=ls))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, color=tc,
            fontweight="bold" if bold else "normal", linespacing=1.15)


def arrow(ax, a, b, color=GREY, style="-|>", rad=0.0, lw=1.2, ls="-"):
    """Arrow from point a to point b; rad bends it (e.g. -0.3 for a feedback loop)."""
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=11, color=color, lw=lw,
                                 connectionstyle=f"arc3,rad={rad}", linestyle=ls))


def sample(out):
    """A generic inputs -> steps -> outputs flow with a review loop."""
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.set_xlim(0, 20); ax.set_ylim(0, 10.4); ax.axis("off")

    ax.text(0.2, 9.9, "INPUTS", fontsize=10, color=BLUE, fontweight="bold")
    for t, x in (("Input A\n(source 1)", 1.0), ("Input B\n(source 2)", 7.4), ("Input C\n(reference)", 13.8)):
        box(ax, x, 8.2, 5.2, 1.4, t, LIGHT, BLUE, size=9.5)

    steps = ["1  Collect", "2  Prepare", "3  Analyse", "4  Review", "5  Publish"]
    w, g, y = 3.4, 0.6, 5.3
    xs = [0.3 + i * (w + g) for i in range(len(steps))]
    for i, (t, x) in enumerate(zip(steps, xs)):
        box(ax, x, y, w, 1.4, t, NAVY, NAVY, tc="white", size=10, bold=True)
        if i < len(steps) - 1:
            arrow(ax, (x + w, y + 0.7), (x + w + g, y + 0.7), color=NAVY, lw=1.6)
    arrow(ax, (3.6, 8.2), (xs[0] + w / 2, y + 1.4))
    arrow(ax, (10.0, 8.2), (xs[1] + w / 2, y + 1.4))
    arrow(ax, (16.4, 8.2), (xs[2] + w / 2, y + 1.4))
    arrow(ax, (xs[3] + w / 2, y), (xs[2] + w / 2, y), color=AMBER, rad=-0.45, lw=1.5, ls="--")
    ax.text((xs[2] + xs[3] + w) / 2, 3.3, "Review feedback loop", ha="center", fontsize=9, color=AMBER, style="italic")

    ax.text(0.2, 2.5, "OUTPUTS", fontsize=10, color=GREEN_D, fontweight="bold")
    for i, t in enumerate(("Output 1", "Output 2", "Output 3")):
        box(ax, 0.3 + i * 6.6, 0.4, 6.0, 1.3, t, GREEN, GREEN_D, size=9.5)
    arrow(ax, (xs[4] + w / 2, y), (xs[4] + w / 2, 1.7), color=GREEN_D, lw=1.6)
    plt.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "figure_style_sample.png"
    sample(out)
    print(f"Wrote {out.name}")
