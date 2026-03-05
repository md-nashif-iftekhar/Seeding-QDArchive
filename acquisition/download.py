"""
download.py — Step 2: Download all files from projects in the database.

Run after search.py:
    python download.py

What it does:
    - Reads every project from qdarchive.db
    - Creates archive/Zenodo/<id>_<title>/ for each project
    - Downloads all files into that folder
    - Saves _metadata.json alongside the files
    - Updates the database with what was actually found
    - Safe to re-run — already-downloaded files are skipped
"""

import json
import os
import re
import time
from pathlib import Path

import requests

from config import (
    DB_PATH, ARCHIVE_DIR, HEADERS,
    REQUEST_TIMEOUT, FILE_DELAY,
    MAX_FILE_SIZE, QDA_EXTENSIONS,
)
from db import init_db, get_all, update_project


# ── Helpers ────────────────────────────────────────────────────────────────────

def safe_dirname(title: str) -> str:
    """Convert a project title to a safe folder name."""
    name = re.sub(r'[\\/*?:"<>|]', "_", title or "unnamed")
    return name[:80].strip()


def download_file(url: str, dest: Path) -> bool:
    """Stream-download one file. Returns True on success."""
    if dest.exists():
        print(f"    [SKIP] Already exists: {dest.name}")
        return True
    try:
        resp = requests.get(url, headers=HEADERS, stream=True, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        size = int(resp.headers.get("Content-Length", 0))
        ext  = dest.suffix.lower()
        if size > MAX_FILE_SIZE and ext not in QDA_EXTENSIONS:
            print(f"    [SKIP] Too large ({size / 1e6:.0f} MB): {dest.name}")
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                total += len(chunk)

        print(f"    [OK]   {dest.name}  ({total / 1e3:.1f} KB)")
        return True

    except Exception as e:
        print(f"    [ERROR] {dest.name}: {e}")
        return False


# ── Zenodo file listing ────────────────────────────────────────────────────────

def get_zenodo_files(source_link: str) -> list[dict]:
    """
    Given a Zenodo HTML link, return [{filename, download_url}] via the API.
    Example link: https://zenodo.org/records/12345
    """
    match = re.search(r"/records?/(\d+)", source_link)
    if not match:
        return []

    record_id = match.group(1)
    try:
        resp = requests.get(
            f"https://zenodo.org/api/records/{record_id}",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return [
            {
                "filename":     f["key"],
                "download_url": f["links"]["self"],
            }
            for f in resp.json().get("files", [])
        ]
    except Exception as e:
        print(f"  [WARN] Could not list files for Zenodo record {record_id}: {e}")
        return []


# ── Per-project download ───────────────────────────────────────────────────────

def download_project(conn, row):
    pid         = row["id"]
    source_link = row["source_link"]
    title       = row["title"]

    folder = Path(ARCHIVE_DIR) / f"{pid:04d}_{safe_dirname(title)}"
    folder.mkdir(parents=True, exist_ok=True)

    print(f"\n[{pid}] {title[:65]}")

    # Save metadata JSON
    meta_path = folder / "_metadata.json"
    if not meta_path.exists():
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(dict(row), f, indent=2, default=str)

    # Get file list from Zenodo API
    files = get_zenodo_files(source_link)
    if not files:
        print(f"  [INFO] No files found for this record.")
        return

    # Download each file
    success   = 0
    qda_found = []

    for finfo in files:
        fname = finfo["filename"]
        furl  = finfo["download_url"]
        ext   = Path(fname).suffix.lower()

        if download_file(furl, folder / fname):
            success += 1
            if ext in QDA_EXTENSIONS:
                qda_found.append(ext)

        time.sleep(FILE_DELAY)

    # Update database
    update_project(conn, pid, {
        "has_qda_files":   1 if qda_found else row["has_qda_files"],
        "qda_file_types":  json.dumps(sorted(set(qda_found))) if qda_found
                           else row["qda_file_types"],
        "has_primary_data": 1 if success > 0 else row["has_primary_data"],
        "file_count":       success,
    })

    print(f"  → {success}/{len(files)} files downloaded"
          + (f"  QDA: {qda_found}" if qda_found else ""))


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] '{DB_PATH}' not found. Run search.py first.")
        return

    Path(ARCHIVE_DIR).mkdir(exist_ok=True)
    conn = init_db(DB_PATH)
    rows = get_all(conn)

    print("=" * 60)
    print("QDArchive — Part 1: Data Acquisition")
    print(f"download.py — Downloading files for {len(rows)} projects")
    print(f"Archive: {Path(ARCHIVE_DIR).resolve()}")
    print("=" * 60)

    for i, row in enumerate(rows, 1):
        print(f"\n--- {i}/{len(rows)} ---")
        try:
            download_project(conn, row)
        except KeyboardInterrupt:
            print("\n[Interrupted] Progress saved to database.")
            break
        except Exception as e:
            print(f"  [SKIP] Unexpected error: {e}")

    conn.close()
    print(f"\n[Done] Files in: {Path(ARCHIVE_DIR).resolve()}")
    print("Next step:  python export.py")


if __name__ == "__main__":
    main()