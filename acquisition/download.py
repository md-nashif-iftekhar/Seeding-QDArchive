import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv
from config import (
    DB_PATH, ARCHIVE_DIR, HEADERS,
    REQUEST_TIMEOUT, FILE_DELAY,
    MAX_FILE_SIZE, QDA_EXTENSIONS,
    REPOSITORIES,
)
from db import (
    init_db,
    get_projects_by_repo,
    get_files_for_project,
    insert_file,
    update_project,
)
load_dotenv()

def safe_dirname(name: str) -> str:
    """Convert any string to a Windows-safe folder name."""
    import unicodedata
    name = name or "unnamed"
    name = "".join(c if unicodedata.category(c) != "Cc" else " " for c in name)
    for ch in r'\/*?:"<>|':
        name = name.replace(ch, "_")
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_. ")[:80]
    return name or "unnamed"

def make_project_folder(repo_name: str,
                        project_folder: str,
                        version_folder: str = None) -> Path:
    parts = [ARCHIVE_DIR, safe_dirname(repo_name), safe_dirname(project_folder)]
    if version_folder:
        parts.append(safe_dirname(version_folder))
    folder = Path(*parts)
    folder.mkdir(parents=True, exist_ok=True)
    return folder

def save_metadata(folder: Path, row) -> None:
    """Save _metadata.json into the project folder."""
    meta_path = folder / "_metadata.json"
    if not meta_path.exists():
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(dict(row), f, indent=2, default=str)
            
def already_downloaded(conn, project_id: int) -> bool:
    """
    Return True only if this project has at least one SUCCEEDED file.
    Projects with only FAILED_* records will be retried.
    """
    files = get_files_for_project(conn, project_id)
    return any(f["status"] == "SUCCEEDED" for f in files)


def stream_download(url: str, dest: Path,
                    session=None) -> str:
    if dest.exists():
        return "SUCCEEDED"

    try:
        requester = session or requests
        resp = requester.get(
            url, headers=HEADERS,
            stream=True, timeout=REQUEST_TIMEOUT,
        )

        if resp.status_code in (401, 403):
            print(f"      [LOGIN]  {dest.name}")
            return "FAILED_LOGIN_REQUIRED"

        if resp.status_code >= 500:
            print(f"      [SERVER] {dest.name} (HTTP {resp.status_code})")
            return "FAILED_SERVER_UNRESPONSIVE"

        resp.raise_for_status()

        # Check file size
        size = int(resp.headers.get("Content-Length", 0))
        ext  = dest.suffix.lower()
        if size > MAX_FILE_SIZE and ext not in QDA_EXTENSIONS:
            print(f"      [LARGE]  {dest.name} ({size/1e6:.0f} MB)")
            return "FAILED_TOO_LARGE"

        # Stream to disk
        dest.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
                total += len(chunk)

        print(f"      [OK]     {dest.name}  ({total/1e3:.1f} KB)")
        return "SUCCEEDED"

    except requests.exceptions.ConnectionError:
        print(f"      [SERVER] {dest.name} (connection error)")
        return "FAILED_SERVER_UNRESPONSIVE"
    except requests.exceptions.Timeout:
        print(f"      [SERVER] {dest.name} (timeout)")
        return "FAILED_SERVER_UNRESPONSIVE"
    except Exception as e:
        print(f"      [SERVER] {dest.name} ({e})")
        return "FAILED_SERVER_UNRESPONSIVE"


#Zenodo

def get_zenodo_files(project_url: str) -> list[dict]:
    match = re.search(r"/records?/(\d+)", project_url)
    if not match:
        return []
    record_id = match.group(1)
    try:
        resp = requests.get(
            f"https://zenodo.org/api/records/{record_id}",
            headers=HEADERS, timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        files = []
        for f in data.get("files", []):
            filename = f.get("key", "")
            if not filename:
                continue
            download_url = (
                f.get("links", {}).get("content")
                or f.get("links", {}).get("self")
                or f"https://zenodo.org/api/records/{record_id}/files/{filename}/content"
            )

            files.append({
                "filename":     filename,
                "download_url": download_url,
            })

        if not files:
            bucket_url = data.get("links", {}).get("bucket")
            if bucket_url:
                bucket_resp = requests.get(
                    bucket_url,
                    headers=HEADERS,
                    timeout=REQUEST_TIMEOUT,
                )
                if bucket_resp.status_code == 200:
                    for f in bucket_resp.json().get("contents", []):
                        filename = f.get("key", "")
                        if filename:
                            files.append({
                                "filename":     filename,
                                "download_url": f.get("links", {}).get("self", ""),
                            })

        return files

    except Exception as e:
        print(f"    [WARN] Could not get file list for {record_id}: {e}")
        return []


def download_zenodo(conn):
    rows = get_projects_by_repo(conn, 1)
    print(f"\n[Zenodo] Downloading {len(rows)} projects…")
    print(f"  Folder: {Path(ARCHIVE_DIR).resolve() / 'zenodo'}")

    for i, row in enumerate(rows, 1):
        pid            = row["id"]
        title          = row["title"]
        project_folder = row["download_project_folder"] or safe_dirname(title)
        version_folder = row["download_version_folder"]

        print(f"\n  [{i}/{len(rows)}] {title[:60]}")
        if already_downloaded(conn, pid):
            print(f"    [SKIP] Already in database.")
            continue

        folder = make_project_folder("zenodo", project_folder, version_folder)
        save_metadata(folder, row)
        files = get_zenodo_files(row["project_url"])
        if not files:
            print(f"    [INFO] No files found.")
            continue

        print(f"    → {folder}")
        print(f"    → {len(files)} files to download")

        for finfo in files:
            fname = finfo["filename"]
            furl  = finfo["download_url"]
            ext   = Path(fname).suffix.lower()

            status = stream_download(furl, folder / fname)
            insert_file(
                conn, pid,
                file_name=fname,
                file_type=ext.lstrip(".") or "unknown",
                status=status,
            )
            time.sleep(FILE_DELAY)
        update_project(conn, pid, {
            "download_date": datetime.utcnow().isoformat()
        })
        project_files = get_files_for_project(conn, pid)
        succeeded = sum(1 for f in project_files if f["status"] == "SUCCEEDED")
        print(f"    Summary: {succeeded}/{len(files)} files succeeded")

    print(f"\n[Zenodo] Done.")

#FSD

def extract_fsd_zip(conn, pid: int, zip_path: Path, folder: Path) -> int:
    import zipfile
    SKIP_EXTENSIONS = {
        ".js", ".css", ".ico", ".woff", ".woff2",
    }

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(folder)

            recorded = 0
            for info in zf.infolist():
                fname = info.filename
                ext   = Path(fname).suffix.lower()

                if fname.endswith("/"):
                    continue

                if ext in SKIP_EXTENSIONS:
                    continue

                if "/html/" in fname.lower():
                    continue

                if "/img/" in fname.lower():
                    continue

                insert_file(
                    conn, pid,
                    file_name=Path(fname).name,
                    file_type=ext.lstrip(".") or "unknown",
                    status="SUCCEEDED",
                )
                recorded += 1

        return recorded

    except zipfile.BadZipFile:
        print(f"      [ERROR] Bad ZIP: {zip_path.name}")
        return 0
    except Exception as e:
        print(f"      [ERROR] Extract failed: {e}")
        return 0


def download_fsd(conn):
    from search.fsd import FSDSearcher, fetch_condition_a_ids

    rows            = get_projects_by_repo(conn, 11)
    repo_name       = REPOSITORIES[11]["name"]
    condition_a_ids = fetch_condition_a_ids()

    print(f"\n[FSD] Processing {len(rows)} projects…")
    print(f"  Condition A ({len(condition_a_ids)} datasets): direct download + extract")
    print(f"  Condition B/C/D : metadata + catalogue link only")

    cond_a_ok   = 0
    cond_a_fail = 0
    cond_other  = 0

    for i, row in enumerate(rows, 1):
        pid            = row["id"]
        title          = row["title"]
        project_folder = row["download_project_folder"] or safe_dirname(title)
        fsd_id         = project_folder  # e.g. FSD3892
        condition      = "A" if fsd_id in condition_a_ids else "B"

        if already_downloaded(conn, pid):
            continue

        conn.execute(
            "DELETE FROM files WHERE project_id=? AND status != 'SUCCEEDED'",
            (pid,)
        )
        conn.commit()

        folder = make_project_folder(repo_name, project_folder)
        save_metadata(folder, row)

        print(f"  [{i}/{len(rows)}] [{condition}] {title[:50]}")

        if condition == "A":
            # Step 1 — download ZIP
            zip_path = folder / f"{fsd_id}.zip"
            status   = FSDSearcher.try_condition_a_download(fsd_id, folder)

            if status == "SUCCEEDED":
                # Step 2 — extract ZIP and record each file individually
                n_files = extract_fsd_zip(conn, pid, zip_path, folder)
                print(f"      → extracted {n_files} files")
                cond_a_ok += 1
            else:
                insert_file(
                    conn, pid,
                    file_name=f"{fsd_id}.zip",
                    file_type="zip",
                    status=status,
                )
                _save_fsd_catalogue_link(folder, row)
                cond_a_fail += 1

        else:
            # Condition B/C/D — save catalogue link for manual download
            insert_file(
                conn, pid,
                file_name="<files_not_downloaded>",
                file_type="unknown",
                status="FAILED_LOGIN_REQUIRED",
            )
            _save_fsd_catalogue_link(folder, row)
            cond_other += 1

        update_project(conn, pid, {
            "download_date": datetime.utcnow().isoformat()
        })

        time.sleep(FILE_DELAY)

    print(f"\n[FSD] Done.")
    print(f"  Condition A downloaded : {cond_a_ok}")
    print(f"  Condition A failed     : {cond_a_fail}")
    print(f"  Condition B/C/D skipped: {cond_other}")
    print(f"  Manual download: https://services.fsd.tuni.fi")


def _save_fsd_catalogue_link(folder, row):
    """Save catalogue_link.txt for manual download."""
    link_file = folder / "catalogue_link.txt"
    if not link_file.exists():
        with open(link_file, "w", encoding="utf-8") as f:
            f.write(f"Title      : {row['title']}\n")
            f.write(f"Project URL: {row['project_url']}\n")
            f.write(f"License    : {row['license'] or 'Unknown'}\n")
            f.write(f"\nManual download instructions:\n")
            f.write(f"1. Go to: {row['project_url']}\n")
            f.write(f"2. Login at: https://services.fsd.tuni.fi\n")
            f.write(f"3. Click Download\n")


#Sikt

def download_sikt(conn):
    rows = get_projects_by_repo(conn, 20)
    repo_name = REPOSITORIES[20]["name"]
    print(f"\n[Sikt] Processing {len(rows)} projects…")
    print(f"  Note: No public download API — no files downloaded.")
    print(f"  Recording FAILED_LOGIN_REQUIRED for all projects.")

    for i, row in enumerate(rows, 1):
        pid            = row["id"]
        title          = row["title"]
        project_folder = row["download_project_folder"] or safe_dirname(title)

        if already_downloaded(conn, pid):
            continue

        folder = make_project_folder(repo_name, project_folder)
        save_metadata(folder, row)
        link_file = folder / "catalogue_link.txt"
        if not link_file.exists():
            with open(link_file, "w", encoding="utf-8") as f:
                f.write(f"Title      : {title}\n")
                f.write(f"Project URL: {row['project_url']}\n")
                f.write(f"DOI        : {row['doi'] or 'N/A'}\n")
                f.write(f"License    : {row['license'] or 'Unknown'}\n")
                f.write(f"\nManual download instructions:\n")
                f.write(f"1. Go to: {row['project_url']}\n")
                f.write(f"2. Login at: https://minforskning.sikt.no\n")
                f.write(f"3. Apply for data access\n")
        insert_file(
            conn, pid,
            file_name="<files_not_downloaded>",
            file_type="unknown",
            status="FAILED_LOGIN_REQUIRED",
        )

        update_project(conn, pid, {
            "download_date": datetime.utcnow().isoformat()
        })

        print(f"  [{i}/{len(rows)}] {title[:55]}")

    print(f"\n[Sikt] Done — metadata saved, files require manual download.")
    print(f"  Order data at: https://sikt.no/en/find-data")

def print_summary(conn):
    """Print archive folder structure and download statistics."""
    from db import summary
    stats = summary(conn)

    print(f"\n{'='*60}")
    print(f"DOWNLOAD COMPLETE")
    print(f"{'='*60}")
    print(f"  Total projects : {stats['total_projects']}")
    print(f"  Total files    : {stats['total_files']}")
    print(f"")
    print(f"  File results:")
    print(f"    SUCCEEDED                  : {stats['files']['succeeded']}")
    print(f"    FAILED_LOGIN_REQUIRED      : {stats['files']['failed_login']}")
    print(f"    FAILED_TOO_LARGE           : {stats['files']['failed_too_large']}")
    print(f"    FAILED_SERVER_UNRESPONSIVE : {stats['files']['failed_server']}")
    print(f"")
    print(f"  By repository:")
    for repo_url, count in stats["by_repository"].items():
        print(f"    {repo_url:<45} {count} projects")

    # Folder structure
    archive = Path(ARCHIVE_DIR)
    print(f"\n  Archive: {archive.resolve()}/")
    if archive.exists():
        for source_dir in sorted(archive.iterdir()):
            if not source_dir.is_dir():
                continue
            subdirs = [d for d in source_dir.iterdir() if d.is_dir()]
            total_files = sum(len(list(d.rglob("*"))) for d in subdirs)
            print(f"    {source_dir.name}/  "
                  f"({len(subdirs)} projects, ~{total_files} files)")

    print(f"{'='*60}")
    print(f"Next step: python export.py")

def parse_args():
    import argparse

    parser = argparse.ArgumentParser(
        description="QDArchive — download files from repositories"
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=["zenodo", "fsd", "sikt"],
        metavar="REPO",
        help="Only download from specified repositories. "
             "Choices: zenodo, fsd, sikt. "
             "Example: --only fsd sikt"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.only:
        run_zenodo = "zenodo" in args.only
        run_fsd    = "fsd"    in args.only
        run_sikt   = "sikt"   in args.only
    else:
        # Default — run all
        run_zenodo = True
        run_fsd    = True
        run_sikt   = True

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] '{DB_PATH}' not found. Run search.py first.")
        return

    Path(ARCHIVE_DIR).mkdir(exist_ok=True)
    conn = init_db(DB_PATH)

    print("=" * 60)
    print("QDArchive — Part 1: Data Acquisition")
    print("download.py — Downloading files")
    print("=" * 60)
    print(f"  Repositories : "
          f"{'Zenodo ' if run_zenodo else ''}"
          f"{'FSD ' if run_fsd else ''}"
          f"{'Sikt' if run_sikt else ''}")
    print("=" * 60)

    if run_zenodo:
        download_zenodo(conn)

    if run_fsd:
        download_fsd(conn)

    if run_sikt:
        download_sikt(conn)

    print_summary(conn)
    conn.close()


if __name__ == "__main__":
    main()