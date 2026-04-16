# Part 1: Data Acquisition — Seeding QDArchive 
**Repositories assigned:** #11 FSD (Finnish Social Science Data Archive), #20 Sikt (Norwegian data archive)

---

## Overview

This automated pipeline discovers, downloads, and catalogs qualitative research data from repositories. It focuses on repositories hosting qualitative datasets such as interview transcripts, field notes, focus group recordings, and QDA files.

### Key Features
- **Qualitative Filtering**: Automatically identifies and prioritizes qualitative datasets
- **Metadata Extraction**: Captures rich metadata including titles, descriptions, DOIs, and licensing
- **Automated Downloads**: Handles authentication, file retrieval, and integrity checks
- **Structured Storage**: Stores metadata in SQLite database with CSV exports

### Architecture Overview

The pipeline consists of three main phases:

1. **Search Phase**: Query repository APIs and catalogs for qualitative datasets
2. **Download Phase**: Authenticate and download identified datasets
3. **Export Phase**: Generate CSV reports and validate data integrity

## Project Structure

```
Seeding-QDArchive/
├── README.md
├── .gitignore
├── acquisition/                       # Main pipeline code
│   ├── config.py
│   ├── db.py
│   ├── search.py
│   ├── download.py
│   ├── export.py
│   ├── fsd_playwright.py
│   ├── sikt_playwright.py
│   ├── requirements.txt
│   ├── qdarchive_*.csv                # Exported data (generated)
│   ├── report.txt                     # Processing report (generated)
│   ├── search/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── fsd.py                     # FSD API integration
│   │   └── sikt.py                    # Sikt API integration
│   └── archive/                       # Downloaded data
│       ├── finnish-social-science-data-archive/
│       └── sikt/
└── venv/                              # Virtual environment (optional)
```

---

## Setup

### Prerequisites
- **Python**: 3.10 or higher
- **Browser**: Google Chrome (for Playwright automation)
- **System**: Windows/Linux/macOS with internet access

### Installation

1. **Clone and navigate**:
```bash
git clone <repository-url>
cd Seeding-QDArchive
```

2. **Create virtual environment** (recommended):
```bash
python -m venv venv
```
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

3. **Install dependencies**:
```bash
cd acquisition
pip install -r requirements.txt
```
---

### Credentials

Create a `.env` file inside the `acquisition/` folder:

```bash
FSD_USERNAME=your_fsd_username
FSD_PASSWORD=your_fsd_password
SIKT_USERNAME=your_sikt_email
SIKT_PASSWORD=your_sikt_password
```

---

## Running the Pipeline

### Full pipeline (fresh start)

# Delete old database if re-running from scratch
```bash
del ..\23240175-seeding.db   # Windows
rm ../23240175-seeding.db    # Linux/Mac
```
# Step 1: Search all repositories (metadata)
```bash
python search.py
```
# Step 2: Download FSD Condition A files (requires Chrome)
```bash
python fsd_playwright.py --only-a
```
# Step 3: Download open Sikt datasets (opens Chrome)
```bash
python sikt_playwright.py
```
# Step 4: Record, saved metadata for restricted datasets
```bash
python download.py --only fsd
python download.py --only sikt
```

# Step 5: Export results
```bash
python export.py
```

### Search individual repositories

```bash
python search.py --only fsd
python search.py --only sikt
```

---

## Database Schema

The pipeline stores all metadata in `23240175-seeding.db` (SQLite) with 5 tables:

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
- FSD requires manual authentication for some datasets
- Large datasets may require multiple download attempts
- Browser automation is sensitive to page layout changes

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