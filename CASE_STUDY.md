# Case study: Multi-Source Job Market Intelligence Tracker

## The problem

Public job boards expose useful hiring data, but different applicant-tracking systems use different field names and structures. Comparing companies manually makes it difficult to see current openings or identify what changed between collection dates.

## The solution

I built a Python pipeline that collects published listings from selected Greenhouse and Lever career boards, converts them into one consistent schema, removes duplicates, classifies workplace arrangements, and compares consecutive snapshots. Each run creates a CSV dataset, a formatted Excel workbook, an HTML summary, and a change report.

## Verified sample result

The corrected run on September 30, 2026 produced:

- 626 current job listings across Cloudflare, Figma, and Spotify
- 547 Greenhouse records and 79 Lever records
- 11 new and 17 removed listings compared with the previous snapshot
- 0 duplicate job keys
- 0 missing titles
- 0 missing application URLs
- 3 of 3 sources collected successfully

These figures describe only the configured public career boards at the time of collection. They are not a complete representation of the job market.

## Reliability work

- Retries and timeouts for temporary API failures
- Source-level isolation so one unavailable board does not cancel other sources
- HTML and illegal control-character cleaning before Excel export
- Source-appropriate publish timestamps (`first_published` for Greenhouse and `createdAt` for Lever)
- Snapshot advancement only after all client-facing reports are generated successfully
- Automated tests for cleaning, timestamps, classification, deduplication, and comparisons

## Deliverables

- Normalized CSV dataset
- Excel workbook with Jobs, Summary, New Jobs, Removed Jobs, and Collection Log sheets
- Browser-friendly HTML report
- Dated snapshots and a new/removed change report

The source configuration contains public board identifiers only. The project does not use paid APIs, credentials, applicant data, LinkedIn, Indeed, or Google Jobs.
