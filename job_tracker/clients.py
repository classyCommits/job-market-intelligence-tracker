"""HTTP clients for supported public applicant-tracking-system endpoints."""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "JobMarketIntelligenceTracker/1.0 (portfolio data project)"
# Control characters that openpyxl refuses to write to worksheets.
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def build_session() -> requests.Session:
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    decoded = html.unescape(str(value))
    if "<" in decoded and ">" in decoded:
        decoded = BeautifulSoup(decoded, "html.parser").get_text(" ", strip=True)
    decoded = CONTROL_CHARS.sub(" ", decoded)
    return re.sub(r"\s+", " ", decoded).strip()


def iso_from_milliseconds(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def classify_workplace(*values: Any) -> str:
    text = " ".join(clean_text(value).lower() for value in values if value)
    if re.search(r"\bhybrid\b", text):
        return "hybrid"
    if re.search(r"\b(remote|distributed|work from home|wfh)\b", text):
        return "remote"
    if re.search(r"\b(on[- ]?site|in[- ]?office)\b", text):
        return "onsite"
    return "unspecified"


def fetch_greenhouse(
    company: str,
    token: str,
    session: requests.Session,
    timeout: int = 30,
) -> list[dict[str, str]]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    response = session.get(url, params={"content": "true"}, timeout=timeout)
    response.raise_for_status()
    jobs = response.json().get("jobs", [])
    collected_at = datetime.now(timezone.utc).isoformat()
    normalized: list[dict[str, str]] = []

    for job in jobs:
        departments = ", ".join(
            item.get("name", "") for item in job.get("departments", []) if item.get("name")
        )
        location = clean_text((job.get("location") or {}).get("name"))
        title = clean_text(job.get("title"))
        description = clean_text(job.get("content"))
        normalized.append(
            {
                "source": "greenhouse",
                "source_job_id": str(job.get("id", "")),
                "company": company,
                "title": title,
                "location": location,
                "department": clean_text(departments),
                "workplace_type": classify_workplace(title, location, description[:500]),
                "employment_type": "",
                "posted_at": clean_text(job.get("first_published") or job.get("updated_at")),
                "job_url": clean_text(job.get("absolute_url")),
                "description": description,
                "collected_at": collected_at,
            }
        )
    return normalized


def fetch_lever(
    company: str,
    token: str,
    session: requests.Session,
    timeout: int = 30,
) -> list[dict[str, str]]:
    url = f"https://api.lever.co/v0/postings/{token}"
    response = session.get(url, params={"mode": "json"}, timeout=timeout)
    response.raise_for_status()
    jobs = response.json()
    collected_at = datetime.now(timezone.utc).isoformat()
    normalized: list[dict[str, str]] = []

    for job in jobs:
        categories = job.get("categories") or {}
        location = clean_text(categories.get("location"))
        title = clean_text(job.get("text"))
        workplace = clean_text(job.get("workplaceType"))
        description = clean_text(job.get("descriptionPlain") or job.get("description"))
        normalized.append(
            {
                "source": "lever",
                "source_job_id": clean_text(job.get("id")),
                "company": company,
                "title": title,
                "location": location,
                "department": clean_text(categories.get("team") or categories.get("department")),
                "workplace_type": classify_workplace(workplace, title, location),
                "employment_type": clean_text(categories.get("commitment")),
                "posted_at": iso_from_milliseconds(job.get("createdAt")),
                "job_url": clean_text(job.get("hostedUrl") or job.get("applyUrl")),
                "description": description,
                "collected_at": collected_at,
            }
        )
    return normalized
