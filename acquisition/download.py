import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from config import (
    DB_PATH, ARCHIVE_DIR, HEADERS,
    REQUEST_TIMEOUT, FILE_DELAY,
    MAX_FILE_SIZE, QDA_EXTENSIONS,
)
from db import init_db, get_all, get_by_source, update_project

load_dotenv()

def safe_dirname(title: str) -> str:
    import unicodedata
    name = title or "unnamed"

    name = "".join(c if unicodedata.category(c) != "Cc" else " " for c in name)

    for ch in r'\/*?:"<>|':
        name = name.replace(ch, "_")

    import re as _re
    name = _re.sub(r"\s+", "_", name)
    name = _re.sub(r"_+", "_", name)
    name = name.strip("_. ")[:80]
    return name or "unnamed"


def make_project_folder(source: str, project_id: int, title: str) -> Path:
    folder = Path(ARCHIVE_DIR) / source / f"{project_id:04d}_{safe_dirname(title)}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_metadata(folder: Path, row) -> None:
    meta_path = folder / "_metadata.json"
    if not meta_path.exists():
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(dict(row), f, indent=2, default=str)


def download_file(url: str, dest: Path, session=None) -> bool:
    if dest.exists():
        print(f"      [SKIP] Already exists: {dest.name}")
        return True
    try:
        requester = session or requests
        resp = requester.get(
            url, headers=HEADERS,
            stream=True, timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()

        size = int(resp.headers.get("Content-Length", 0))
        ext  = dest.suffix.lower()
        if size > MAX_FILE_SIZE and ext not in QDA_EXTENSIONS:
            print(f"      [SKIP] Too large ({size/1e6:.0f} MB): {dest.name}")
            return False

        total = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                total += len(chunk)

        print(f"      [OK]   {dest.name}  ({total/1e3:.1f} KB)")
        return True

    except Exception as e:
        print(f"      [ERROR] {dest.name}: {e}")
        return False

def get_zenodo_files(source_link: str) -> list[dict]:
    """API"""
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
            {"filename": f["key"], "download_url": f["links"]["self"]}
            for f in resp.json().get("files", [])
        ]
    except Exception as e:
        print(f"    [WARN] Could not get Zenodo files for {record_id}: {e}")
        return []


def download_zenodo(conn):
    rows = get_by_source(conn, "Zenodo")
    print(f"\n[Zenodo] Downloading {len(rows)} projects…")
    print(f"  Folder: {Path(ARCHIVE_DIR).resolve() / 'Zenodo'}")

    for i, row in enumerate(rows, 1):
        pid   = row["id"]
        title = row["title"]
        print(f"\n  [{i}/{len(rows)}] {title[:60]}")

        folder = make_project_folder("Zenodo", pid, title)
        print(f"    → {folder}")

        save_metadata(folder, row)

        files = get_zenodo_files(row["source_link"])
        if not files:
            print(f"    [INFO] No files found for this record.")
            continue

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

        update_project(conn, pid, {
            "has_qda_files":    1 if qda_found else row["has_qda_files"],
            "qda_file_types":   json.dumps(sorted(set(qda_found)))
                                if qda_found else row["qda_file_types"],
            "has_primary_data": 1 if success > 0 else row["has_primary_data"],
            "file_count":       success,
        })

        print(f"    Summary: {success}/{len(files)} files downloaded"
              + (f"  |  QDA: {qda_found}" if qda_found else ""))

    print(f"\n[Zenodo] Done.")

def download_fsd(conn):
    rows = get_by_source(conn, "FSD")
    print(f"\n[FSD] Processing {len(rows)} projects…")
    print(f"  Folder: {Path(ARCHIVE_DIR).resolve() / 'FSD'}")
    print(f"  Note: FSD uses Shibboleth SSO — saving metadata + catalogue links.")

    for i, row in enumerate(rows, 1):
        pid   = row["id"]
        title = row["title"]

        folder = make_project_folder("FSD", pid, title)
        save_metadata(folder, row)

        # Extract FSD study ID from raw_metadata
        fsd_id = ""
        try:
            meta   = eval(row["raw_metadata"] or "{}")
            fsd_id = meta.get("fsd_id", "")
        except Exception:
            pass

        link_file = folder / "catalogue_link.txt"
        if not link_file.exists():
            with open(link_file, "w") as f:
                f.write(f"Title      : {title}\n")
                f.write(f"FSD ID     : {fsd_id}\n")
                f.write(f"Catalogue  : {row['source_link']}\n")
                f.write(f"Download   : {row['download_url']}\n")
                f.write(f"\nTo download manually:\n")
                f.write(f"1. Go to: {row['source_link']}\n")
                f.write(f"2. Login with your FSD credentials\n")
                f.write(f"3. Click Download\n")

        print(f"  [{i}/{len(rows)}] {title[:55]}  →  {folder.name}")

    print(f"\n[FSD] Done — metadata and catalogue links saved for {len(rows)} projects.")
    print(f"  To download files manually, login at: https://services.fsd.tuni.fi")

def download_sikt(conn):
    rows = get_by_source(conn, "Sikt")
    print(f"\n[Sikt] Processing {len(rows)} projects…")
    print(f"  Folder: {Path(ARCHIVE_DIR).resolve() / 'Sikt'}")
    print(f"  Note: No public download API — saving metadata + catalogue links.")

    for i, row in enumerate(rows, 1):
        pid   = row["id"]
        title = row["title"]

        folder = make_project_folder("Sikt", pid, title)
        save_metadata(folder, row)
        link_file = folder / "catalogue_link.txt"
        if not link_file.exists():
            with open(link_file, "w") as f:
                f.write(f"Title      : {title}\n")
                f.write(f"Catalogue  : {row['source_link']}\n")
                f.write(f"\nTo download manually:\n")
                f.write(f"1. Go to: {row['source_link']}\n")
                f.write(f"2. Login at: https://minforskning.sikt.no\n")
                f.write(f"3. Apply for data access\n")

        print(f"  [{i}/{len(rows)}] {title[:55]}  →  {folder.name}")

    print(f"\n[Sikt] Done — metadata and catalogue links saved for {len(rows)} projects.")
    print(f"  To order data manually, go to: https://sikt.no/en/find-data")

def print_folder_summary():
    """Print the final folder structure created."""
    archive = Path(ARCHIVE_DIR)
    print(f"\n{'='*60}")
    print(f"ARCHIVE FOLDER STRUCTURE")
    print(f"{'='*60}")
    print(f"{archive.resolve()}/")

    for source_dir in sorted(archive.iterdir()):
        if not source_dir.is_dir():
            continue
        subdirs = [d for d in source_dir.iterdir() if d.is_dir()]
        files_total = sum(
            len(list(d.iterdir())) for d in subdirs
        )
        print(f"├── {source_dir.name}/  ({len(subdirs)} projects, {files_total} files)")
        for j, project_dir in enumerate(sorted(subdirs)[:5]):
            prefix = "│   └──" if j == len(subdirs[:5]) - 1 else "│   ├──"
            fcount = len(list(project_dir.iterdir()))
            print(f"{prefix} {project_dir.name}/  ({fcount} files)")
        if len(subdirs) > 5:
            print(f"│   └── ... and {len(subdirs)-5} more projects")

    print(f"{'='*60}")

def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] '{DB_PATH}' not found. Run search.py first.")
        return

    Path(ARCHIVE_DIR).mkdir(exist_ok=True)
    conn = init_db(DB_PATH)

    print("=" * 60)
    print("QDArchive — Part 1: Data Acquisition")
    print("download.py — Downloading files")
    print("=" * 60)

    download_zenodo(conn)
    download_fsd(conn)
    download_sikt(conn)

    conn.close()

    print_folder_summary()

    print(f"\nNext step:  python export.py")


if __name__ == "__main__":
    main()