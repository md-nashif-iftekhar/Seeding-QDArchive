## Project Structure

```
qdarchive/
│
├── acquisition/                  
│   ├── config.py                 — all settings & constants
│   ├── db.py                     — database operations
│   ├── search/
│   │   ├── __init__.py           — exports ALL_SEARCHERS
│   │   ├── base.py               — shared HTTP & helper logic
│   │   └── zenodo.py             — Zenodo API searcher
│   │
│   ├── search.py                 — Step 1: search & collect metadata
│   ├── download.py               — Step 2: download files
│   ├── export.py                 — Step 3: export CSV + report
│   ├── requirements.txt
│   │
│   ├── qdarchive_export.csv      — generated (submitted)
│   └── report.txt                — generated (statistics)
│
├── part2_classification/         
│   └── ...
│
├── part3_analysis/               
│   └── ...
│
├── .gitignore
└── README.md
```

---

## Part 1: Acquisition

### Setup

```bash
cd acquisition
pip install -r requirements.txt
```

### Run

```bash
# Step 1 — Search Zenodo, collect metadata into qdarchive.db
python search.py

# Step 2 — Download all files into archive/
python download.py

# Step 3 — Export CSV and generate report
python export.py
```

### Output

| File | Description |
|------|-------------|
| `qdarchive.db` | SQLite database (all metadata) |
| `qdarchive_export.csv` | CSV export — submitted via form |
| `report.txt` | Statistics summary |
| `archive/` | All downloaded project files — submitted via link |

---

## Git Workflow

| Branch | Purpose |
|--------|---------|
| `main` | Stable, merged work only |
| `part1/acquisition` | Part 1 development |
| `part2/classification` | Part 2 development |
| `part3/analysis` | Part 3 development |

### Submission tags

```bash
git tag part-1-release && git push origin part-1-release
git tag part-2-release && git push origin part-2-release
git tag part-3-release && git push origin part-3-release
```