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


if __name__ == "__main__":
    main()
