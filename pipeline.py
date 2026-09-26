"""A reproducible multi-source, micro-batch BI pipeline using only Python's stdlib."""

from __future__ import annotations

import argparse
import csv
import html
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

EVENT_FIELDS = ("event_id", "account_id", "event_date", "event_type", "amount_usd")
ACCOUNT_FIELDS = ("account_id", "region", "segment")
TARGET_FIELDS = ("region", "daily_revenue_target_usd")
REGIONS = ("East", "Midwest", "South", "West")


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def generate_sources(directory: Path, count: int = 5000, seed: int = 42) -> None:
    if count < 10:
        raise ValueError("count must be at least 10")
    rng = random.Random(seed)
    accounts = [
        {"account_id": f"SYN-ACC-{i:04d}", "region": rng.choice(REGIONS), "segment": rng.choice(("SMB", "Mid-market", "Enterprise"))}
        for i in range(1, 201)
    ]
    targets = [{"region": region, "daily_revenue_target_usd": 5000} for region in REGIONS]
    events = []
    start = date(2026, 1, 1)
    for i in range(count):
        kind = rng.choices(("purchase", "refund", "visit"), weights=(4, 1, 10))[0]
        amount = round(rng.uniform(15, 500), 2) if kind != "visit" else 0.0
        events.append(
            {
                "event_id": f"SYN-EVT-{i + 1:07d}",
                "account_id": rng.choice(accounts)["account_id"],
                "event_date": (start + timedelta(days=rng.randrange(30))).isoformat(),
                "event_type": kind,
                "amount_usd": amount,
            }
        )
    # Known exceptions make validation and deduplication visible to reviewers.
    events.append(dict(events[0]))
    events.append({"event_id": "SYN-EVT-BAD", "account_id": "SYN-ACC-9999", "event_date": "2026-01-10", "event_type": "purchase", "amount_usd": 50})
    write_csv(directory / "accounts.csv", ACCOUNT_FIELDS, accounts)
    write_csv(directory / "targets.csv", TARGET_FIELDS, targets)
    write_csv(directory / "events.csv", EVENT_FIELDS, events)


def read_csv(path: Path, expected: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(expected):
            raise ValueError(f"Invalid schema: {path}")
        return list(reader)


def run_pipeline(source_dir: Path, output_dir: Path, batch_size: int = 500) -> dict[str, int | str]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    accounts = read_csv(source_dir / "accounts.csv", ACCOUNT_FIELDS)
    targets = read_csv(source_dir / "targets.csv", TARGET_FIELDS)
    events = read_csv(source_dir / "events.csv", EVENT_FIELDS)
    account_map = {row["account_id"]: row for row in accounts}
    target_map = {row["region"]: float(row["daily_revenue_target_usd"]) for row in targets}
    if len(account_map) != len(accounts) or set(target_map) != set(REGIONS):
        raise ValueError("Duplicate accounts or missing region targets")
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE facts (event_id TEXT PRIMARY KEY, account_id TEXT, event_date TEXT, "
        "region TEXT, segment TEXT, event_type TEXT, signed_revenue REAL)"
    )
    exceptions: list[dict[str, str]] = []
    seen: set[str] = set()
    loaded = 0
    for offset in range(0, len(events), batch_size):
        batch = events[offset : offset + batch_size]
        accepted = []
        for row in batch:
            event_id = row["event_id"]
            reason = ""
            if not event_id.startswith("SYN-EVT-"):
                reason = "invalid_id"
            elif event_id in seen:
                reason = "duplicate_id"
            elif row["account_id"] not in account_map:
                reason = "unknown_account"
            elif row["event_type"] not in ("purchase", "refund", "visit"):
                reason = "invalid_type"
            else:
                try:
                    date.fromisoformat(row["event_date"])
                    amount = float(row["amount_usd"])
                    if amount < 0 or (row["event_type"] == "visit" and amount != 0):
                        reason = "invalid_amount"
                except ValueError:
                    reason = "invalid_date_or_amount"
            if reason:
                exceptions.append({"event_id": event_id, "reason": reason})
                continue
            seen.add(event_id)
            account = account_map[row["account_id"]]
            signed = -amount if row["event_type"] == "refund" else amount
            accepted.append(
                (event_id, row["account_id"], row["event_date"], account["region"], account["segment"], row["event_type"], signed)
            )
        with connection:
            connection.executemany("INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?, ?)", accepted)
        loaded += len(accepted)

    summary = connection.execute(
        "SELECT event_date, region, COUNT(*) AS events, "
        "SUM(CASE WHEN event_type='purchase' THEN 1 ELSE 0 END) AS purchases, "
        "ROUND(SUM(signed_revenue), 2) AS net_revenue_usd "
        "FROM facts GROUP BY event_date, region ORDER BY event_date, region"
    ).fetchall()
    kpis = [
        {
            "event_date": day,
            "region": region,
            "events": event_count,
            "purchases": purchases,
            "net_revenue_usd": net,
            "daily_target_usd": target_map[region],
            "target_attainment_pct": round(100 * net / target_map[region], 1),
        }
        for day, region, event_count, purchases, net in summary
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "daily_kpis.csv", tuple(kpis[0]), kpis)
    write_csv(output_dir / "exceptions.csv", ("event_id", "reason"), exceptions)
    totals = connection.execute("SELECT COUNT(*), ROUND(SUM(signed_revenue), 2) FROM facts").fetchone()
    report = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Pipeline run summary</title><style>
body{{font:16px/1.5 system-ui,sans-serif;background:#101521;color:#edf4ff;max-width:850px;margin:0 auto;padding:40px 24px}}
h1{{font-size:clamp(2rem,6vw,3.5rem)}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:16px;margin:30px 0}}
.card{{background:#19263a;border:1px solid #334761;border-radius:16px;padding:20px}}strong{{display:block;font-size:2rem;color:#6ddbd6}}.note{{color:#a6b8cf}}
table{{border-collapse:collapse;width:100%}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #334761}}
</style><main><p class="note">SYNTHETIC MULTI-SOURCE MICRO-BATCH DEMO</p><h1>Pipeline run summary</h1><p>Generated data only. This local run is not connected to live business systems.</p>
<div class="cards"><div class="card">Events loaded<strong>{loaded:,}</strong></div><div class="card">Exceptions<strong>{len(exceptions):,}</strong></div><div class="card">Net revenue<strong>${totals[1]:,.0f}</strong></div></div>
<h2>Quality gate</h2><table><tr><th>Reason</th><th>Count</th></tr>{''.join(f'<tr><td>{html.escape(reason)}</td><td>{sum(e["reason"] == reason for e in exceptions)}</td></tr>' for reason in sorted({e['reason'] for e in exceptions}))}</table>
<p class="note">Detailed daily measures and rejected events are in the generated CSV files.</p></main></html>"""
    (output_dir / "run_summary.html").write_text(report, encoding="utf-8")
    connection.close()
    return {"source_events": len(events), "loaded_events": loaded, "exceptions": len(exceptions), "output": str(output_dir)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=Path("outputs/sources"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/report"))
    parser.add_argument("--events", type=int, default=5000)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not (args.source_dir / "events.csv").exists():
        generate_sources(args.source_dir, args.events, args.seed)
    print(run_pipeline(args.source_dir, args.output_dir, args.batch_size))
