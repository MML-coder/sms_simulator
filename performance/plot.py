"""Draw the benchmark charts from bench.sh output.

Usage: uv run --group bench performance/plot.py [results file]   (default: performance/results/m2.txt)
Writes PNGs to performance/plots/.
"""

import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).parent
OUT = HERE / "plots"

# Categorical slots in fixed order; text stays in neutral ink, never series colour.
BLUE, ORANGE, GRAY = "#2a78d6", "#eb6834", "#8a8984"
SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

FIELD = re.compile(r"(\w+)=([\d.]+)")


def parse(path: Path) -> dict[str, list[dict[str, float]]]:
    """Group result lines by section letter (A, B, C) into dicts of their numeric fields."""
    sections: dict[str, list[dict[str, float]]] = defaultdict(list)
    section = None
    for line in path.read_text().splitlines():
        if line.startswith("## "):
            section = line[3]
        elif section in ("A", "B", "C") and "final" in line:
            sections[section].append({k: float(v) for k, v in FIELD.findall(line)})
    return sections


def style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.set_facecolor(SURFACE)
    ax.grid(True, which="major", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, which="both")


def thousands(value: float, _pos) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:g}M"
    if value >= 1_000:
        return f"{value / 1_000:g}k"
    return f"{value:g}"


def by_senders(rows: list[dict[str, float]], field: str) -> tuple[list[float], list[list[float]]]:
    groups: dict[float, list[float]] = defaultdict(list)
    for row in rows:
        groups[row["senders"]].append(row[field])
    senders = sorted(groups)
    return senders, [groups[s] for s in senders]


def scatter_runs(ax, senders: list[float], runs: list[list[float]], color: str) -> None:
    """Every individual run as a small hollow dot, behind the median line."""
    for s, values in zip(senders, runs):
        ax.scatter([s] * len(values), values, s=60, facecolors="none", edgecolors=color, linewidths=1, zorder=2)


def throughput(sections, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=SURFACE)
    a, b = sections["A"], sections["B"]

    senders_a = [r["senders"] for r in a]
    ax.plot(senders_a, [r["expected"] for r in a], color=GRAY, linestyle="--", linewidth=2,
            label="Expected with 10 ms sends (senders ÷ 10 ms)", zorder=1)
    ax.plot(senders_a, [r["rate"] for r in a], color=BLUE, linewidth=2, marker="o", markersize=7,
            label="Measured, 10 ms mean send time", zorder=3)

    senders_b, runs_b = by_senders(b, "rate")
    scatter_runs(ax, senders_b, runs_b, ORANGE)
    ax.plot(senders_b, [statistics.median(v) for v in runs_b], color=ORANGE, linewidth=2, marker="o",
            markersize=4, label="Measured, no send delay (line = median, rings = each of 3 runs)", zorder=3)

    ceiling = max(statistics.median(v) for v in runs_b)
    ax.annotate(f"ceiling ≈ {ceiling / 1000:.0f}k/s", (senders_b[2], ceiling), xytext=(0, 12),
                textcoords="offset points", ha="center", color=INK, fontsize=9)
    last = a[-1]
    ax.annotate(f"{last['rate'] / 1000:.0f}k/s\nloop saturated", (last["senders"], last["rate"]),
                xytext=(6, -34), textcoords="offset points", ha="right", color=INK, fontsize=9)

    ax.set_xscale("log")
    ax.set_yscale("log")
    for axis in (ax.xaxis, ax.yaxis):
        axis.set_major_formatter(FuncFormatter(thousands))
    style(ax, "Throughput vs senders", "Senders (log scale)", "Messages per second (log scale)")
    ax.legend(loc="lower right", frameon=False, labelcolor=INK, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def send_time(sections, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5), facecolor=SURFACE)
    a, b = sections["A"], sections["B"]

    ax.plot([r["senders"] for r in a], [r["avg"] for r in a], color=BLUE, linewidth=2, marker="o",
            markersize=7, label="10 ms mean send time", zorder=3)
    senders_b, runs_b = by_senders(b, "avg")
    scatter_runs(ax, senders_b, runs_b, ORANGE)
    ax.plot(senders_b, [statistics.median(v) for v in runs_b], color=ORANGE, linewidth=2, marker="o",
            markersize=4, label="No send delay (line = median, rings = each of 3 runs)", zorder=3)
    ax.axhline(10, color=GRAY, linestyle="--", linewidth=1.5, label="Configured mean, 10 ms", zorder=1)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(thousands))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g} ms"))
    style(ax, "Measured send time vs senders",
          "Senders (log scale)", "Average measured send time (log scale)")
    ax.legend(loc="upper left", frameon=False, labelcolor=INK, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def memory(sections, path: Path) -> None:
    fig, (left, right) = plt.subplots(1, 2, figsize=(10, 4.5), facecolor=SURFACE, sharey=True)
    c = sections["C"]
    left.plot([r["messages"] for r in c], [r["rss"] for r in c], color=BLUE, linewidth=2, marker="o", markersize=7)
    left.set_xscale("log")
    left.xaxis.set_major_formatter(FuncFormatter(thousands))
    style(left, "Peak memory vs messages (100 senders)", "Messages (log scale)", "Peak RSS (MB)")

    senders_b, runs_b = by_senders(sections["B"], "rss")
    right.plot(senders_b, [statistics.median(v) for v in runs_b], color=BLUE, linewidth=2, marker="o", markersize=7)
    right.set_xscale("log")
    right.xaxis.set_major_formatter(FuncFormatter(thousands))
    style(right, "Peak memory vs senders (1M messages)", "Senders (log scale)", "")

    left.set_ylim(0, max(max(v) for v in runs_b) * 1.15)
    for ax, xs, ys in ((left, [c[-1]["messages"]], [c[-1]["rss"]]),
                       (right, [senders_b[-1]], [statistics.median(runs_b[-1])])):
        ax.annotate(f"{ys[0]:.1f} MB", (xs[0], ys[0]), xytext=(-8, 8), textcoords="offset points",
                    ha="right", color=INK, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    results = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results" / "m2.txt"
    sections = parse(results)
    OUT.mkdir(exist_ok=True)
    throughput(sections, OUT / "throughput.png")
    send_time(sections, OUT / "send_time.png")
    memory(sections, OUT / "memory.png")
    print(f"wrote {', '.join(p.name for p in sorted(OUT.glob('*.png')))} to {OUT}")


if __name__ == "__main__":
    main()
