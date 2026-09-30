# Product requirements document: Job Market Intelligence Tracker

## 1. Product summary

The Job Market Intelligence Tracker is a portfolio-sized data pipeline that collects publicly listed jobs from company career boards using the official Greenhouse Job Board API and Lever Postings API. It converts different source formats into one clean dataset, removes duplicates, classifies workplace arrangements, compares the latest run with the previous snapshot, and produces presentation-ready CSV, Excel, and HTML outputs.

The project is intended to demonstrate a complete freelance data workflow rather than operate as a commercial job board.

## 2. Problem

Job listings from different applicant-tracking systems use inconsistent field names and structures. A researcher or recruiting team must repeatedly visit separate company pages to understand:

- which roles are open;
- where companies are hiring;
- which roles are remote or hybrid;
- which departments are growing; and
- which listings appeared or disappeared since the last collection.

## 3. Target user

The primary user is a market researcher, recruiter, founder, or job-market analyst who wants a compact, repeatable view of public job listings across selected companies.

## 4. Goals

1. Collect published jobs from configured Greenhouse and Lever career boards without paid APIs.
2. Normalize every listing into a consistent schema.
3. Remove exact and likely cross-source duplicates.
4. Produce outputs that a non-technical client can inspect immediately.
5. Preserve dated snapshots and identify new and removed listings on later runs.
6. Fail gracefully when one configured source is unavailable.

## 5. Non-goals

- Scraping LinkedIn, Indeed, Google Jobs, or other restricted aggregators
- Submitting job applications
- Collecting applicant or personal data
- Continuous cloud hosting or real-time alerts
- Inferring salary where a source does not publish it
- Claiming that the configured companies represent the whole job market

## 6. Data sources

The MVP supports:

- Greenhouse Job Board API public `GET` endpoints
- Lever Postings API public job-listing endpoints

Sources are selected in `config/sources.json`. No credentials are required.

## 7. Normalized job schema

| Field | Description |
| --- | --- |
| `job_key` | Stable internal identifier used for snapshot comparison |
| `source` | `greenhouse` or `lever` |
| `source_job_id` | Identifier supplied by the source |
| `company` | Display name from configuration |
| `title` | Published job title |
| `location` | Primary published location |
| `department` | Department or team when supplied |
| `workplace_type` | `remote`, `hybrid`, `onsite`, or `unspecified` |
| `employment_type` | Commitment/type when supplied |
| `posted_at` | Source timestamp when supplied |
| `job_url` | Public listing URL |
| `description` | Plain-text description, whitespace normalized |
| `collected_at` | UTC collection timestamp |

## 8. Functional requirements

### FR1: Configuration

- Read a JSON configuration file containing enabled sources.
- Validate platform, company name, and board token/site name.
- Permit sources to be disabled without code changes.

### FR2: Collection

- Fetch public jobs with a timeout, retry policy, and descriptive user agent.
- Continue processing other sources if one source fails.
- Record collection success, failure, and row counts.

### FR3: Normalization

- Map Greenhouse and Lever responses into the normalized schema.
- Strip HTML from descriptions and normalize whitespace.
- Classify workplace type conservatively from explicit source values and location/title text.

### FR4: Quality controls

- Remove exact duplicates by source and source job ID.
- Remove likely duplicates using normalized company, title, and location.
- Reject records without a title or public URL.
- Sort output predictably by company, title, and location.

### FR5: Snapshot comparison

- Save the latest normalized dataset as `latest_jobs.csv`.
- Archive a timestamped CSV snapshot for every successful run.
- Compare the current dataset with the previous snapshot.
- Export new and removed listings.

### FR6: Deliverables

Each run must create:

- `latest_jobs.csv`
- `job_market_report.xlsx`
- `report.html`
- `changes.csv`
- a dated file inside `snapshots/`

The Excel workbook must contain Jobs, Summary, New Jobs, Removed Jobs, and Collection Log sheets.

## 9. Success criteria

The MVP is accepted when:

- at least two configured sources can be collected in one command;
- one source failure does not cancel successful sources;
- all accepted records follow the normalized schema;
- duplicate keys are absent from the final dataset;
- CSV, Excel, HTML, change report, and snapshot outputs are generated;
- automated tests cover normalization, workplace classification, deduplication, and snapshot comparison;
- setup and execution are documented in the README;
- the repository contains no API keys, cookies, personal data, or bulk proprietary datasets.

## 10. Portfolio presentation

The Contra case study should show:

1. Greenhouse and Lever sources flowing into one Python pipeline.
2. The normalized Jobs worksheet.
3. The Summary worksheet or HTML report.
4. The New Jobs and Removed Jobs comparison.

The presentation must describe the data as a time-stamped sample of selected public company career boards, not a complete view of the labor market.

## 11. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A company changes ATS or board identifier | Keep sources configurable and log failures without aborting the run |
| Source fields are missing | Use explicit blank values rather than inventing data |
| Rate limiting or temporary errors | Apply timeouts, retries, and a small delay between requests |
| Listings change between screenshots | Preserve dated snapshots and state the collection time |
| Misleading analytics | Report counts only for configured sources and label the sample clearly |

## 12. Delivery phases

### Phase 1: MVP

Configuration, collection, normalization, deduplication, CSV/Excel/HTML reports, snapshots, change detection, tests, and documentation.

### Phase 2: Optional improvements

Salary parsing, keyword groups, scheduled execution, email alerts, and additional ATS adapters may be added later. They are not required for the Contra sample.
