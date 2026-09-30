# Job Market Intelligence Tracker

A portfolio-sized Python pipeline that combines public job listings from Greenhouse and Lever career boards into a consistent dataset, removes duplicates, creates summary analytics, and compares consecutive snapshots.

No paid API or API key is required.

## What the project demonstrates

- Multi-source data collection
- API response normalization
- Data cleaning and deduplication
- Workplace-type classification
- Snapshot-based change detection
- Client-ready CSV, Excel, and HTML reporting
- Retries, timeouts, source-level error isolation, and automated tests

The product definition and acceptance criteria are in [PRD.md](PRD.md).
The verified portfolio outcome is documented in [CASE_STUDY.md](CASE_STUDY.md).

## Outputs

Running the pipeline creates:

| File | Purpose |
| --- | --- |
| `output/latest_jobs.csv` | Complete normalized dataset from the latest run |
| `output/job_market_report.xlsx` | Jobs, summary, changes, and collection log |
| `output/report.html` | Browser-friendly portfolio report |
| `output/changes.csv` | New and removed listings compared with the previous snapshot |
| `output/snapshots/jobs_*.csv` | Dated datasets used for later comparisons |

The first run marks all collected listings as new because no previous snapshot exists.

## Setup on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## Run

```powershell
.\.venv\Scripts\python.exe run_pipeline.py
```

To use another configuration or output location:

```powershell
.\.venv\Scripts\python.exe run_pipeline.py --config config/sources.json --output-dir output
```

## Test

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Configure sources

Edit `config/sources.json`:

```json
{
  "platform": "greenhouse",
  "company": "Example Company",
  "token": "company-board-token",
  "enabled": true
}
```

For Greenhouse, `token` is the public board token in the company's Greenhouse URL. For Lever, it is the public site name in its Lever jobs URL. Invalid or retired boards are logged as failed while the remaining sources continue.

## Responsible use

This project reads published listings from official public job-board endpoints. It does not scrape LinkedIn, Indeed, Google Jobs, applicant information, or private recruiting data. Reports represent only the configured companies at the collection time.
