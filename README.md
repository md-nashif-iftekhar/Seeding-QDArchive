# Part 1: Data Acquisition — Seeding QDArchive

**Course:** Applied Software Engineering Seminar/Project  
**University:** Friedrich-Alexander-Universität Erlangen-Nürnberg (FAU)  
**Supervisor:** Prof. Dr. Dirk Riehle  
**Student:** Md Nashif Iftekhar  
**Repositories assigned:** #11 Finnish Social Science Data Archive (FSD), #20 Sikt  
**Zenodo (#1) implemented as supplement**

---

## Overview

This pipeline automatically searches qualitative research data repositories, downloads available files, and stores metadata in a structured SQLite database. It targets repositories that archive qualitative research data such as interview transcripts, fieldnotes, and QDA project files.

---

## Repositories

| # | Name | URL | Method | Status |
|---|------|-----|--------|--------|
| 1 | Zenodo | https://zenodo.org | REST API | ✅ Full automated download |
| 11 | FSD (Finnish Social Science Data Archive) | https://www.fsd.tuni.fi/en | OAI-PMH + Playwright | ✅ Condition A downloaded |
| 20 | Sikt (Norwegian data archive) | https://sikt.no/en/find-data | CESSDA OAI-PMH | ⚠️ See technical note below |

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
│   ├── zenodo.py           # Zenodo REST API searcher
│   ├── fsd.py              # FSD OAI-PMH + catalogue scraper
│   └── sikt.py             # Sikt CESSDA OAI-PMH searcher
└── archive/                # Downloaded files (not in git)
    ├── zenodo/
    ├── finnish-social-science-data-archive/
    └── sikt/
```

---

## Setup

### Requirements

- Python 3.10+
- Google Chrome (for FSD Playwright downloader)

### Installation

```bash
pip install -r requirements.txt
playwright install chromium
```

### Credentials

Create a `.env` file in the `acquisition/` folder:

```
FSD_USERNAME=your_fsd_username
FSD_PASSWORD=your_fsd_password
```

---

## Running the Pipeline

### Full pipeline (fresh start)

```bash
# Delete old database if re-running from scratch
del qdarchive.db   # Windows
rm qdarchive.db    # Linux/Mac

# Step 1: Search all repositories
python search.py

# Step 2: Download Zenodo files
python download.py --only zenodo

# Step 3: Download FSD Condition A files (requires Chrome)
python fsd_playwright.py --only-a

# Step 4: Record metadata for FSD Condition B/C/D and Sikt
python download.py --only fsd
python download.py --only sikt

# Step 5: Export results
python export.py
```

### Search individual repositories

```bash
python search.py --only zenodo
python search.py --only fsd
python search.py --only sikt
```

### Download individual repositories

```bash
python download.py --only zenodo
python download.py --only fsd
python download.py --only sikt
```

---

## Database Schema

The pipeline stores all metadata in `qdarchive.db` (SQLite) with 4 tables:

**`projects`** — one row per research project  
**`files`** — one row per file (download result)  
**`keywords`** — one row per keyword tag  
**`person_role`** — one row per author/uploader

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
├── zenodo/
│   └── {record_id}/
│       ├── _metadata.json
│       └── {files...}
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

## FSD Download Details

FSD uses Shibboleth SSO for authentication. The download approach depends on the access condition:

| Condition | Description | Download method |
|-----------|-------------|-----------------|
| A | CC BY 4.0, freely available | ✅ Automated via Playwright |
| B | Research, teaching and study | ⚠️ Playwright with purpose form |
| C | Research only | ⚠️ Manual |
| D | Depositor permission required | ❌ Manual only |

**Condition A datasets (7 confirmed):**
FSD3892, FSD3847, FSD3524, FSD3208, FSD3166, FSD2981, FSD1249

The pipeline dynamically scrapes the FSD catalogue to detect Condition A datasets:
```
https://services.fsd.tuni.fi/catalogue/index
    ?dissemination_policy_string_facet=A
    &data_kind_string_facet=Qualitative
```

---

## Technical Challenges

### FSD — Shibboleth SSO
The `/v0/download/` URL redirects to the FSD homepage without a valid browser session — even for Condition A (CC BY 4.0) datasets. The FSD requires a browser-based SAML login flow that cannot be completed with plain HTTP requests. Solution: Playwright browser automation handles the full SSO chain including the "Information Release" consent page.

### FSD — Condition detection from OAI-PMH
The OAI-PMH `dc:type` field is always empty and `dc:rights` always contains the same generic text regardless of condition. Condition A/B/C/D is only visible in the HTML catalogue page, not in the OAI-PMH metadata.

### Sikt — API unavailable (April 2026)
The SIKT set was removed from the CESSDA OAI-PMH catalogue. After investigation:
- CESSDA OAI-PMH: SIKT set no longer exists (45,418 records from other providers, 0 from Sikt)
- Surveybanken (surveybanken.sikt.no): JavaScript-rendered, no public JSON API
- Legacy NSD OAI-PMH: returns HTML, not OAI-PMH XML

This is documented as a technical challenge. Sikt metadata is only accessible via browser at https://surveybanken.sikt.no.

### Zenodo — InvenioRDM API migration
Zenodo migrated to InvenioRDM which changed the API parameters. `sort=bestmatch` and `size=100` cause `400 BAD REQUEST`. Fixed by removing `sort` parameter and setting `size=25` (maximum allowed).

---

## Exported Files

After running `export.py`:

| File | Contents |
|------|---------|
| `qdarchive_projects.csv` | All projects with metadata |
| `qdarchive_files.csv` | All files with download status |
| `qdarchive_keywords.csv` | All keywords |
| `qdarchive_persons.csv` | All persons with roles |
| `report.txt` | Human-readable summary |

---

## Results Summary

| Repository | Projects | Files downloaded |
|-----------|----------|-----------------|
| Zenodo | ~82,250 | ~4,747 |
| FSD Condition A | 7 | ~200 (extracted from ZIPs) |
| FSD Condition B/C/D | ~575 | 0 (catalogue links saved) |
| Sikt | 0 | 0 (API unavailable) |