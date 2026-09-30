"""Collection, quality control, snapshot comparison, and report generation."""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .clients import build_session, fetch_greenhouse, fetch_lever

COLUMNS = [
    "job_key",
    "source",
    "source_job_id",
    "company",
    "title",
    "location",
    "department",
    "workplace_type",
    "employment_type",
    "posted_at",
    "job_url",
    "description",
    "collected_at",
]


def slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def make_job_key(record: dict[str, Any]) -> str:
    source_identity = "|".join(
        [slug(record.get("source")), slug(record.get("company")), slug(record.get("source_job_id"))]
    )
    if not slug(record.get("source_job_id")):
        source_identity = "|".join(
            [slug(record.get("company")), slug(record.get("title")), slug(record.get("location"))]
        )
    return hashlib.sha256(source_identity.encode("utf-8")).hexdigest()[:16]


def normalize_and_deduplicate(records: list[dict[str, Any]]) -> pd.DataFrame:
    prepared: list[dict[str, str]] = []
    for record in records:
        item = {column: str(record.get(column, "") or "").strip() for column in COLUMNS if column != "job_key"}
        if not item["title"] or not item["job_url"]:
            continue
        item["job_key"] = make_job_key(item)
        prepared.append(item)

    if not prepared:
        return pd.DataFrame(columns=COLUMNS)

    frame = pd.DataFrame(prepared, columns=COLUMNS)
    frame["dedupe_key"] = (
        frame["company"].map(slug) + "|" + frame["title"].map(slug) + "|" + frame["location"].map(slug)
    )
    frame = frame.drop_duplicates(subset=["job_key"], keep="first")
    frame = frame.drop_duplicates(subset=["dedupe_key"], keep="first")
    frame = frame.drop(columns="dedupe_key")
    return frame.sort_values(["company", "title", "location"], kind="stable").reset_index(drop=True)


def compare_snapshots(current: pd.DataFrame, previous: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    current_keys = set(current.get("job_key", pd.Series(dtype=str)).astype(str))
    previous_keys = set(previous.get("job_key", pd.Series(dtype=str)).astype(str))
    new_jobs = current[current["job_key"].astype(str).isin(current_keys - previous_keys)].copy()
    removed_jobs = previous[previous["job_key"].astype(str).isin(previous_keys - current_keys)].copy()
    return new_jobs, removed_jobs


def summary_tables(jobs: pd.DataFrame) -> dict[str, pd.DataFrame]:
    def counts(column: str, label: str) -> pd.DataFrame:
        if jobs.empty:
            return pd.DataFrame(columns=[label, "jobs"])
        values = jobs[column].replace("", "Unspecified").fillna("Unspecified")
        result = values.value_counts().rename_axis(label).reset_index(name="jobs")
        return result

    return {
        "Companies": counts("company", "company"),
        "Workplace": counts("workplace_type", "workplace_type"),
        "Departments": counts("department", "department").head(15),
        "Locations": counts("location", "location").head(15),
    }


def autosize_and_style(worksheet) -> None:
    header_fill = PatternFill("solid", fgColor="17365D")
    for cell in worksheet[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(vertical="center")
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions
    for index, column in enumerate(worksheet.columns, start=1):
        values = [str(cell.value or "") for cell in list(column)[:200]]
        width = min(max(max((len(value) for value in values), default=8) + 2, 10), 45)
        worksheet.column_dimensions[get_column_letter(index)].width = width


def write_excel(
    path: Path,
    jobs: pd.DataFrame,
    new_jobs: pd.DataFrame,
    removed_jobs: pd.DataFrame,
    collection_log: pd.DataFrame,
) -> None:
    summaries = summary_tables(jobs)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        jobs.to_excel(writer, sheet_name="Jobs", index=False)
        new_jobs.to_excel(writer, sheet_name="New Jobs", index=False)
        removed_jobs.to_excel(writer, sheet_name="Removed Jobs", index=False)
        collection_log.to_excel(writer, sheet_name="Collection Log", index=False)

        start_row = 2
        summary_sheet = writer.book.create_sheet("Summary")
        summary_sheet["A1"] = "Job Market Intelligence Summary"
        summary_sheet["A1"].font = Font(size=16, bold=True, color="17365D")
        summary_sheet["A2"] = "Scope: configured public company career boards only"
        summary_sheet["A4"] = "Total jobs"
        summary_sheet["B4"] = len(jobs)
        summary_sheet["A5"] = "New since previous snapshot"
        summary_sheet["B5"] = len(new_jobs)
        summary_sheet["A6"] = "Removed since previous snapshot"
        summary_sheet["B6"] = len(removed_jobs)

        start_row = 8
        table_positions: dict[str, int] = {}
        for name, table in summaries.items():
            table_positions[name] = start_row
            summary_sheet.cell(start_row, 1, name).font = Font(bold=True, color="17365D")
            for col_idx, column_name in enumerate(table.columns, start=1):
                cell = summary_sheet.cell(start_row + 1, col_idx, column_name)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="17365D")
            for row_idx, row in enumerate(table.itertuples(index=False), start=start_row + 2):
                for col_idx, value in enumerate(row, start=1):
                    summary_sheet.cell(row_idx, col_idx, value)
            start_row += len(table) + 4

        company_table = summaries["Companies"]
        if not company_table.empty:
            top = table_positions["Companies"] + 1
            chart = BarChart()
            chart.title = "Jobs by company"
            chart.y_axis.title = "Jobs"
            chart.x_axis.title = "Company"
            data = Reference(summary_sheet, min_col=2, min_row=top, max_row=top + len(company_table))
            categories = Reference(summary_sheet, min_col=1, min_row=top + 1, max_row=top + len(company_table))
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(categories)
            chart.height = 7
            chart.width = 13
            summary_sheet.add_chart(chart, "E4")

        summary_sheet.column_dimensions["A"].width = 42
        summary_sheet.column_dimensions["B"].width = 14

        for name in ("Jobs", "New Jobs", "Removed Jobs", "Collection Log"):
            autosize_and_style(writer.book[name])


def write_html(
    path: Path,
    jobs: pd.DataFrame,
    new_jobs: pd.DataFrame,
    removed_jobs: pd.DataFrame,
    collection_log: pd.DataFrame,
) -> None:
    summaries = summary_tables(jobs)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cards = "".join(
        f'<div class="card"><strong>{value}</strong><span>{label}</span></div>'
        for label, value in (
            ("current jobs", len(jobs)),
            ("new jobs", len(new_jobs)),
            ("removed jobs", len(removed_jobs)),
            ("companies", jobs["company"].nunique() if not jobs.empty else 0),
        )
    )
    sections = []
    for title, table in summaries.items():
        sections.append(f"<section><h2>{title}</h2>{table.to_html(index=False, border=0)}</section>")
    preview_columns = ["company", "title", "location", "workplace_type", "department", "job_url"]
    preview = jobs[preview_columns].head(50).copy() if not jobs.empty else pd.DataFrame(columns=preview_columns)
    html_document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Market Intelligence Report</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f7fb;color:#14213d}}main{{max-width:1180px;margin:auto;padding:32px}}
h1{{margin-bottom:4px}}.sub{{color:#5b677a;margin-top:0}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin:24px 0}}
.card,section{{background:white;border:1px solid #dce3ec;border-radius:12px;padding:18px;box-shadow:0 3px 12px rgba(20,33,61,.05)}}
.card strong{{display:block;font-size:30px;color:#0b6e69}}.card span{{color:#5b677a}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:18px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #e7ebf0;vertical-align:top}}th{{background:#17365d;color:white}}
.jobs{{margin-top:20px;overflow-x:auto}}.note{{font-size:13px;color:#667085;margin-top:24px}}
</style></head><body><main><h1>Job Market Intelligence Report</h1><p class="sub">Selected public career boards · generated {generated}</p>
<div class="cards">{cards}</div><div class="grid">{''.join(sections)}</div>
<section class="jobs"><h2>Job preview</h2>{preview.to_html(index=False, border=0, render_links=True, escape=True)}</section>
<section class="jobs"><h2>Collection log</h2>{collection_log.to_html(index=False, border=0)}</section>
<p class="note">This report is a time-stamped portfolio sample from configured public company career boards. It is not a complete representation of the job market.</p>
</main></body></html>"""
    path.write_text(html_document, encoding="utf-8")


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    sources = config.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("Configuration must include a non-empty 'sources' list")
    for source in sources:
        if source.get("platform") not in {"greenhouse", "lever"}:
            raise ValueError(f"Unsupported platform: {source.get('platform')}")
        if not source.get("company") or not source.get("token"):
            raise ValueError("Every source requires company and token values")
    return config


def previous_snapshot(snapshot_dir: Path) -> pd.DataFrame:
    snapshots = sorted(snapshot_dir.glob("jobs_*.csv"))
    if not snapshots:
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(snapshots[-1], dtype=str).fillna("")


def run_pipeline(config_path: Path, output_dir: Path) -> dict[str, Any]:
    config = load_config(config_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir = output_dir / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    previous = previous_snapshot(snapshot_dir)

    session = build_session()
    records: list[dict[str, str]] = []
    logs: list[dict[str, Any]] = []
    delay = max(float(config.get("request_delay_seconds", 0.25)), 0)

    for source in config["sources"]:
        if not source.get("enabled", True):
            continue
        started = datetime.now(timezone.utc).isoformat()
        try:
            if source["platform"] == "greenhouse":
                result = fetch_greenhouse(source["company"], source["token"], session)
            else:
                result = fetch_lever(source["company"], source["token"], session)
            records.extend(result)
            logs.append({"company": source["company"], "platform": source["platform"], "status": "success", "jobs": len(result), "message": "", "started_at": started})
        except Exception as exc:  # source isolation is a product requirement
            logs.append({"company": source["company"], "platform": source["platform"], "status": "failed", "jobs": 0, "message": str(exc), "started_at": started})
        time.sleep(delay)

    jobs = normalize_and_deduplicate(records)
    if jobs.empty:
        raise RuntimeError("No valid jobs were collected; inspect the collection log or source configuration")

    new_jobs, removed_jobs = compare_snapshots(jobs, previous)
    collected_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    snapshot_path = snapshot_dir / f"jobs_{collected_stamp}.csv"
    jobs.to_csv(output_dir / "latest_jobs.csv", index=False, encoding="utf-8-sig")

    changes = pd.concat(
        [new_jobs.assign(change="new"), removed_jobs.assign(change="removed")],
        ignore_index=True,
    )
    change_columns = ["change", *COLUMNS]
    changes.reindex(columns=change_columns).to_csv(output_dir / "changes.csv", index=False, encoding="utf-8-sig")
    log_frame = pd.DataFrame(logs)
    write_excel(output_dir / "job_market_report.xlsx", jobs, new_jobs, removed_jobs, log_frame)
    write_html(output_dir / "report.html", jobs, new_jobs, removed_jobs, log_frame)
    # Only advance the comparison baseline after every client-facing report succeeds.
    jobs.to_csv(snapshot_path, index=False, encoding="utf-8-sig")

    return {
        "jobs": len(jobs),
        "new_jobs": len(new_jobs),
        "removed_jobs": len(removed_jobs),
        "successful_sources": int((log_frame["status"] == "success").sum()),
        "failed_sources": int((log_frame["status"] == "failed").sum()),
        "snapshot": str(snapshot_path),
    }
