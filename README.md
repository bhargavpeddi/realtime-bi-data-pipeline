# Real-Time BI & Data Engineering Pipeline — micro-batch demo

This is a runnable reconstruction of the multi-source ETL and BI workflow described on my resume. It generates three synthetic sources (events, accounts, regional targets), processes events in configurable micro-batches, checks quality, deduplicates IDs, joins dimensions, aggregates KPIs in SQLite, and writes dashboard-ready CSV plus an HTML run summary.

The original work involved operational data; **none of that data or code is included here**. This demonstration is not a live stream or production service. “Real-time” in the resume describes the original project; this repository illustrates the pipeline mechanics with local micro-batches.

## Run it

Python 3.9+; no third-party packages required.

```bash
python3 pipeline.py
python3 -m unittest -v
```

Open `outputs/report/run_summary.html`, and inspect `daily_kpis.csv` and `exceptions.csv`. The generator deliberately inserts a duplicate and an unknown account to make the rejection path observable. `python3 pipeline.py --help` lists batch size and source options.

## What this shows, and what it does not

The demo uses deterministic generated data, explicit schema checks, row-level exception reasons, transactionally loaded batches, and reproducible KPI exports. A production pipeline would additionally need durable checkpoints, idempotent retries across restarts, secrets management, orchestration, observability, access control, and freshness SLAs. The CSV exports can be imported into Power BI or Tableau; no native dashboard file is claimed here.
