"""Plot daily net revenue by region from outputs/report/daily_kpis.csv. Requires matplotlib."""

import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


def main(report_dir: Path = Path("outputs/report"), docs_dir: Path = Path("docs")) -> None:
    series: dict[str, list[tuple[date, float]]] = defaultdict(list)
    target = 0.0
    with (report_dir / "daily_kpis.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            series[row["region"]].append((date.fromisoformat(row["event_date"]), float(row["net_revenue_usd"])))
            target = float(row["daily_target_usd"])
    docs_dir.mkdir(exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 5))
    for region, points in sorted(series.items()):
        ax.plot([d for d, _ in points], [v for _, v in points], linewidth=2, label=region)
    ax.axhline(target, linestyle="--", color="#6b7280", linewidth=1.2, label="Daily target")
    ax.axhline(0, color="#9aa4b2", linewidth=0.8)
    ax.set_ylim(top=target * 1.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.set_title("Daily net revenue by region", loc="left", fontweight="bold")
    ax.set_ylabel("Net revenue (USD)")
    ax.legend(ncol=5, frameon=False, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(docs_dir / "daily_revenue.png", dpi=120)
    print(f"Wrote {docs_dir / 'daily_revenue.png'}")


INK, MUTED, GRID, SURFACE = "#1f2328", "#6b7280", "#e5e7eb", "#fcfcfb"
BLUE, ORANGE = "#2a78d6", "#eb6834"


def read_kpis(report_dir: Path) -> list[dict[str, str]]:
    with (report_dir / "daily_kpis.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=MUTED)


def attainment_chart(report_dir: Path, docs_dir: Path) -> None:
    """Average daily target attainment per region, against the 100% target."""
    by_region: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_kpis(report_dir):
        by_region[row["region"]].append(row)
    stats = []
    for region, rows in by_region.items():
        avg = sum(float(r["target_attainment_pct"]) for r in rows) / len(rows)
        total = sum(float(r["net_revenue_usd"]) for r in rows)
        stats.append((region, avg, total, len(rows)))
    stats.sort(key=lambda item: item[1])

    fig, ax = plt.subplots(figsize=(10, 5.5), facecolor=SURFACE)
    style(ax)
    names = [s[0] for s in stats]
    ax.barh(names, [s[1] for s in stats], color=BLUE, height=0.6)
    for y, (_, avg, total, days) in enumerate(stats):
        ax.text(avg + 1.5, y, f"{avg:.1f}%  (${total:,.0f} over {days} days)", va="center", color=INK, fontsize=10)
    ax.axvline(100, color=MUTED, linestyle="--", linewidth=1.5)
    ax.text(99, -0.62, "daily target ", color=MUTED, fontsize=10, va="center", ha="right")
    ax.set_ylim(-0.85, len(stats) - 0.5)
    ax.set_xlim(0, 105)
    ax.set_xlabel("Average daily target attainment (%)", color=INK)
    ax.set_title("Average daily target attainment by region", loc="left", fontweight="bold", color=INK)
    ax.tick_params(axis="y", colors=INK, length=0)
    ax.grid(axis="x", alpha=0.6, color=GRID)
    fig.tight_layout()
    fig.savefig(docs_dir / "target_attainment.png", dpi=200)


def attainment_heatmap(report_dir: Path, docs_dir: Path) -> None:
    """Target attainment for every region and day; days with negative net revenue in orange."""
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import Patch

    rows = read_kpis(report_dir)
    regions = sorted({r["region"] for r in rows})
    days = sorted({r["event_date"] for r in rows})
    value = {(r["region"], r["event_date"]): float(r["target_attainment_pct"]) for r in rows}

    ramp = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab"])
    fig, ax = plt.subplots(figsize=(12, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for y, region in enumerate(regions):
        for x, day in enumerate(days):
            v = value.get((region, day))
            if v is None:
                continue
            color = ORANGE if v < 0 else ramp(min(v, 100) / 100)
            ax.add_patch(plt.Rectangle((x + 0.04, y + 0.06), 0.92, 0.88, color=color, linewidth=0))
    ax.set_xlim(0, len(days))
    ax.set_ylim(len(regions), 0)
    ax.set_yticks([i + 0.5 for i in range(len(regions))], regions, color=INK)
    ticks = list(range(0, len(days), 5))
    ax.set_xticks([t + 0.5 for t in ticks], [date.fromisoformat(days[t]).strftime("%b %d") for t in ticks], color=MUTED)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    sm = plt.cm.ScalarMappable(cmap=ramp, norm=plt.Normalize(0, 100))
    bar = fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.02)
    bar.set_label("Target attainment (%)", color=INK)
    bar.outline.set_visible(False)
    bar.ax.tick_params(colors=MUTED)
    ax.legend(handles=[Patch(color=ORANGE, label="Refunds exceeded purchases")], frameon=False,
              loc="upper right", bbox_to_anchor=(1.0, 1.16), fontsize=10)
    ax.set_title("Daily target attainment, region by day", loc="left", fontweight="bold", color=INK, pad=14)
    fig.tight_layout()
    fig.savefig(docs_dir / "attainment_heatmap.png", dpi=200)


if __name__ == "__main__":
    main()
    attainment_chart(Path("outputs/report"), Path("docs"))
    attainment_heatmap(Path("outputs/report"), Path("docs"))
    print("Wrote docs/target_attainment.png and docs/attainment_heatmap.png")
