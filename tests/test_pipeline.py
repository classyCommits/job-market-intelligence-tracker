from __future__ import annotations

import pandas as pd

from job_tracker.clients import classify_workplace, clean_text, fetch_greenhouse, iso_from_milliseconds
from job_tracker.pipeline import COLUMNS, compare_snapshots, normalize_and_deduplicate


def record(**overrides):
    base = {
        "source": "greenhouse",
        "source_job_id": "123",
        "company": "Example Co",
        "title": "Data Analyst",
        "location": "Remote - US",
        "department": "Data",
        "workplace_type": "remote",
        "employment_type": "Full-time",
        "posted_at": "2026-01-01T00:00:00Z",
        "job_url": "https://example.com/jobs/123",
        "description": "Analyze data",
        "collected_at": "2026-01-02T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_clean_text_removes_html_and_normalizes_whitespace():
    assert clean_text("<p>Hello&nbsp; <strong>world</strong></p>") == "Hello world"


def test_clean_text_removes_excel_illegal_control_characters():
    assert clean_text("Copied\x00from\x08Word\x1b safely") == "Copied from Word safely"


def test_greenhouse_prefers_first_published_timestamp():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "jobs": [
                    {
                        "id": 7,
                        "title": "Analyst",
                        "location": {"name": "London"},
                        "departments": [{"name": "Data"}],
                        "content": "Analyze data",
                        "first_published": "2026-01-02T03:04:05Z",
                        "updated_at": "2026-09-30T12:00:00Z",
                        "absolute_url": "https://example.com/jobs/7",
                    }
                ]
            }

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    jobs = fetch_greenhouse("Example", "example", Session())
    assert jobs[0]["posted_at"] == "2026-01-02T03:04:05Z"


def test_workplace_classification_is_conservative():
    assert classify_workplace("Senior Engineer", "Remote - Canada") == "remote"
    assert classify_workplace("Designer", "New York (Hybrid)") == "hybrid"
    assert classify_workplace("Support", "In-office") == "onsite"
    assert classify_workplace("Analyst", "London") == "unspecified"


def test_millisecond_timestamp_conversion():
    assert iso_from_milliseconds(0) == "1970-01-01T00:00:00+00:00"
    assert iso_from_milliseconds("bad") == ""


def test_deduplicates_same_role_and_rejects_incomplete_records():
    duplicate = record(source="lever", source_job_id="xyz", job_url="https://example.com/jobs/xyz")
    incomplete = record(source_job_id="missing", title="", job_url="")
    frame = normalize_and_deduplicate([record(), duplicate, incomplete])
    assert list(frame.columns) == COLUMNS
    assert len(frame) == 1
    assert frame.iloc[0]["title"] == "Data Analyst"


def test_snapshot_comparison_finds_new_and_removed_jobs():
    current = normalize_and_deduplicate([record(), record(source_job_id="456", title="Engineer", job_url="https://example.com/jobs/456")])
    previous = normalize_and_deduplicate([record(), record(source_job_id="789", title="Designer", job_url="https://example.com/jobs/789")])
    new_jobs, removed_jobs = compare_snapshots(current, previous)
    assert new_jobs["title"].tolist() == ["Engineer"]
    assert removed_jobs["title"].tolist() == ["Designer"]


def test_empty_input_has_stable_schema():
    assert normalize_and_deduplicate([]).equals(pd.DataFrame(columns=COLUMNS))
