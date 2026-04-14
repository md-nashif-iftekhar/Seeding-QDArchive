# Part 1: Data Acquisition — Seeding QDArchive

**Course:** Applied Software Engineering Seminar/Project  
**University:** Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU)  
**Supervisor:** Prof. Dr. Dirk Riehle  
**Student:** Md Nashif Iftekhar  
**Repositories assigned:** #11 FSD (Finnish Social Science Data Archive), #20 Sikt (Norwegian data archive)

---

## Overview

This pipeline automatically searches qualitative research data repositories, downloads available files, and stores metadata in a structured SQLite database. It targets repositories that archive qualitative research data such as interview transcripts, fieldnotes, and QDA project files.


---

## Project Structure

```
acquisition/
├── search.py               # Step 1: Search repositories, harvest metadata
├── download.py             # Step 2: Download files
├── export.py               # Step 3: Export database to CSV
├── fsd_playwright.py       # FSD Condition A/B downloader via Playwright
├── config.py               # Configuration: URLs, queries, file types
├── db.py                   # SQLite database schema and functions
├── requirements.txt        # Python dependencies
├── search/
│   ├── fsd.py              # FSD OAI-PMH + catalogue scraper
│   └── sikt.py             # Sikt CESSDA OAI-PMH searcher
└── archive/                # Downloaded files (not in git)
    ├── finnish-social-science-data-archive/
    └── sikt/
```

---

## Setup

### Requirements

- Python 3.10+
- Google Chrome (for Playwright)

### Installation

```bash
cd acquisition
pip install -r requirements.txt
playwright install chromium
```

### Credentials

Create a `.env` file in the `acquisition/` folder:

```
FSD_USERNAME=your_fsd_username
FSD_PASSWORD=your_fsd_password
SIKT_USERNAME=your_sikt_email
SIKT_PASSWORD=your_sikt_password
```

---

## Running the Pipeline

### Full pipeline (fresh start)

```bash
# Delete old database if re-running from scratch
del ..\23240175-seeding.db   # Windows
rm ../23240175-seeding.db    # Linux/Mac

# Step 1: Search all repositories (metadata)
python search.py

# Step 2: Download FSD Condition A files (requires Chrome)
python fsd_playwright.py --only-a

# Step 3: Download open Sikt datasets (opens Chrome)
python sikt_playwright.py

# Step 4: Record, saved metadata for restricted datasets
python download.py --only fsd
python download.py --only sikt

# Step 5: Export results
python export.py
```

### Search individual repositories

```bash
python search.py --only fsd
python search.py --only sikt
```

### Download individual repositories

```bash
python download.py --only fsd
python download.py --only sikt
```

---

## Database Schema

The pipeline stores all metadata in `qdarchive.db` (SQLite) with 5 tables:

**`projects`** — one row per research project  
**`files`** — one row per file (download result)  
**`keywords`** — one row per keyword tag  
**`person_role`** — one row per author/uploader
**`licenses`** — License per project

### File download statuses

| Status | Meaning |
|--------|---------|
| `SUCCEEDED` | File downloaded successfully |
| `FAILED_LOGIN_REQUIRED` | Login or access agreement required |
| `FAILED_TOO_LARGE` | File exceeds size limit |
| `FAILED_SERVER_UNRESPONSIVE` | Server did not respond |

---

## Archive Folder Structure

```
archive/
├── finnish-social-science-data-archive/
│   └── {FSD_ID}/
│       ├── _metadata.json
│       ├── {FSD_ID}.zip          (Condition A only)
│       ├── {FSD_ID}/             (extracted contents)
│       └── catalogue_link.txt    (Condition B/C/D)
└── sikt/
    └── {NSD_ID}/
        ├── _metadata.json
        └── catalogue_link.txt
```

---

## Technical Challenges

### FSD — Shibboleth SSO
Direct download URLs redirect to homepage without a browser session. The `/v0/download/` URL redirects to the FSD homepage without a valid browser session — even for Condition A (CC BY 4.0) datasets. The FSD requires a browser-based SAML login flow that cannot be completed with plain HTTP requests.
Solution: Solved with Playwright handling the full SAML chain including the "Information Release" consent page.

### FSD — Condition detection from OAI-PMH
The OAI-PMH `dc:type` field is always empty and `dc:rights` always contains the same generic text regardless of condition. Condition A/B/C/D is only visible in the HTML catalogue page, not in the OAI-PMH metadata.
Solution: Solved by scraping the HTML catalogue with `dissemination_policy_string_facet=A`.

### Sikt — API unavailable (April 2026)
The SIKT set was removed from the CESSDA OAI-PMH catalogue. After investigation:
- CESSDA OAI-PMH: SIKT set no longer exists.
- Discovered a GraphQL API at api.nsd.no/graphql as replacement.
- Surveybanken (surveybanken.sikt.no): JavaScript-rendered, no public JSON API
- Legacy NSD OAI-PMH: returns HTML, not OAI-PMH XML

### Sikt — Download form:
Automated the download form (Purpose, Institution, Data Citation checkbox) using Playwright with JavaScript clicks to bypass overlay issues.