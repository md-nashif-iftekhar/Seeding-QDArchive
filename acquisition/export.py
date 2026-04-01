import csv
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from config import DB_PATH, ARCHIVE_DIR, REPORT_PATH
from db import init_db, summary

EXPORT_PROJECTS  = "qdarchive_projects.csv"
EXPORT_FILES     = "qdarchive_files.csv"
EXPORT_KEYWORDS  = "qdarchive_keywords.csv"
EXPORT_PERSONS   = "qdarchive_persons.csv"

def export_projects(conn: sqlite3.Connection) -> int:
    """Export PROJECTS table to CSV. Returns row count."""
    rows = conn.execute("""
        SELECT
            id,
            query_string,
            repository_id,
            repository_url,
            project_url,
            version,
            title,
            description,
            language,
            doi,
            upload_date,
            download_date,
            download_repository_folder,
            download_project_folder,
            download_version_folder,
            download_method,
            license,
            license_url
        FROM projects
        ORDER BY repository_id, id
    """).fetchall()

    with open(EXPORT_PROJECTS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "query_string", "repository_id", "repository_url",
            "project_url", "version", "title", "description",
            "language", "doi", "upload_date", "download_date",
            "download_repository_folder", "download_project_folder",
            "download_version_folder", "download_method",
            "license", "license_url",
        ])
        writer.writerows(rows)

    print(f"  → {EXPORT_PROJECTS}  ({len(rows)} rows)")
    return len(rows)


def export_files(conn: sqlite3.Connection) -> int:
    """Export FILES table to CSV. Returns row count."""
    rows = conn.execute("""
        SELECT
            f.id,
            f.project_id,
            p.repository_id,
            p.repository_url,
            p.project_url,
            f.file_name,
            f.file_type,
            f.status
        FROM files f
        JOIN projects p ON f.project_id = p.id
        ORDER BY f.project_id, f.id
    """).fetchall()

    with open(EXPORT_FILES, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "project_id", "repository_id", "repository_url",
            "project_url", "file_name", "file_type", "status",
        ])
        writer.writerows(rows)

    print(f"  → {EXPORT_FILES}  ({len(rows)} rows)")
    return len(rows)


def export_keywords(conn: sqlite3.Connection) -> int:
    """Export KEYWORDS table to CSV. Returns row count."""
    rows = conn.execute("""
        SELECT
            k.id,
            k.project_id,
            p.repository_id,
            p.project_url,
            k.keyword
        FROM keywords k
        JOIN projects p ON k.project_id = p.id
        ORDER BY k.project_id, k.id
    """).fetchall()

    with open(EXPORT_KEYWORDS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "project_id", "repository_id",
            "project_url", "keyword",
        ])
        writer.writerows(rows)

    print(f"  → {EXPORT_KEYWORDS}  ({len(rows)} rows)")
    return len(rows)


def export_persons(conn: sqlite3.Connection) -> int:
    """Export PERSON_ROLE table to CSV. Returns row count."""
    rows = conn.execute("""
        SELECT
            pr.id,
            pr.project_id,
            p.repository_id,
            p.project_url,
            pr.name,
            pr.role
        FROM person_role pr
        JOIN projects p ON pr.project_id = p.id
        ORDER BY pr.project_id, pr.id
    """).fetchall()

    with open(EXPORT_PERSONS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "id", "project_id", "repository_id",
            "project_url", "name", "role",
        ])
        writer.writerows(rows)

    print(f"  → {EXPORT_PERSONS}  ({len(rows)} rows)")
    return len(rows)

def write_report(conn: sqlite3.Connection,
                 n_projects: int,
                 n_files: int,
                 n_keywords: int,
                 n_persons: int):
    """Write human-readable report.txt."""
    stats = summary(conn)
    now   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # File status breakdown
    file_stats = conn.execute("""
        SELECT status, COUNT(*) as cnt
        FROM files
        GROUP BY status
        ORDER BY cnt DESC
    """).fetchall()

    # Top keywords
    top_keywords = conn.execute("""
        SELECT keyword, COUNT(*) as cnt
        FROM keywords
        GROUP BY keyword
        ORDER BY cnt DESC
        LIMIT 20
    """).fetchall()

    # Per-repo breakdown
    repo_stats = conn.execute("""
        SELECT
            p.repository_id,
            p.repository_url,
            COUNT(DISTINCT p.id)              as projects,
            COUNT(f.id)                       as files,
            SUM(CASE WHEN f.status='SUCCEEDED'
                     THEN 1 ELSE 0 END)       as succeeded,
            SUM(CASE WHEN f.status LIKE 'FAILED%'
                     THEN 1 ELSE 0 END)       as failed
        FROM projects p
        LEFT JOIN files f ON f.project_id = p.id
        GROUP BY p.repository_id
        ORDER BY p.repository_id
    """).fetchall()

    lines = [
        "=" * 60,
        "QDArchive — Part 1: Data Acquisition Report",
        f"Generated : {now}",
        "=" * 60,
        "",
        "OVERVIEW",
        "-" * 40,
        f"  Total projects  : {n_projects:,}",
        f"  Total files     : {n_files:,}",
        f"  Total keywords  : {n_keywords:,}",
        f"  Total persons   : {n_persons:,}",
        "",
        "FILE DOWNLOAD RESULTS",
        "-" * 40,
    ]

    for row in file_stats:
        lines.append(f"  {row[0]:<35} {row[1]:>6}")

    lines += [
        "",
        "BY REPOSITORY",
        "-" * 40,
    ]

    for row in repo_stats:
        lines.append(f"  Repo #{row[0]} — {row[1]}")
        lines.append(f"    Projects : {row[2]:,}")
        lines.append(f"    Files    : {row[3]:,}")
        lines.append(f"    Succeeded: {row[4] or 0:,}")
        lines.append(f"    Failed   : {row[5] or 0:,}")
        lines.append("")

    lines += [
        "REPOSITORY NOTES",
        "-" * 40,
        "  Repo #1  — Zenodo",
        "    Full automated download via REST API.",
        "    No login required.",
        "",
        "  Repo #11 — FSD (Finnish Social Science Data Archive)",
        "    Metadata harvested via OAI-PMH.",
        "    File download NOT automatable:",
        "    FSD uses Shibboleth SSO which cannot be scripted",
        "    programmatically. Even with valid credentials,",
        "    login requires a browser-based SAML flow.",
        "    Status: FAILED_LOGIN_REQUIRED for all FSD files.",
        "",
        "  Repo #20 — Sikt (Norwegian data archive)",
        "    Metadata harvested via CESSDA OAI-PMH.",
        "    File download NOT automatable:",
        "    No public download API exists. Files require a",
        "    signed data access agreement per dataset via",
        "    minforskning.sikt.no.",
        "    Status: FAILED_LOGIN_REQUIRED for all Sikt files.",
        "",
        "TOP 20 KEYWORDS",
        "-" * 40,
    ]

    for kw, cnt in top_keywords:
        lines.append(f"  {kw:<40} {cnt:>5}")

    lines += [
        "",
        "EXPORTED FILES",
        "-" * 40,
        f"  {EXPORT_PROJECTS}",
        f"  {EXPORT_FILES}",
        f"  {EXPORT_KEYWORDS}",
        f"  {EXPORT_PERSONS}",
        f"  {REPORT_PATH}",
        "",
        "ARCHIVE FOLDER",
        "-" * 40,
        f"  {Path(ARCHIVE_DIR).resolve()}",
        "",
        "=" * 60,
    ]

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"  → {REPORT_PATH}")

def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] '{DB_PATH}' not found. Run search.py and download.py first.")
        return

    conn = init_db(DB_PATH)

    print("=" * 60)
    print("QDArchive — Part 1: Data Acquisition")
    print("export.py — Exporting to CSV")
    print("=" * 60)
    print(f"\nExporting all 4 tables…")

    n_projects = export_projects(conn)
    n_files    = export_files(conn)
    n_keywords = export_keywords(conn)
    n_persons  = export_persons(conn)

    print(f"\nWriting report…")
    write_report(conn, n_projects, n_files, n_keywords, n_persons)

    conn.close()

    print(f"\n{'='*60}")
    print(f"EXPORT COMPLETE")
    print(f"{'='*60}")
    print(f"  Projects  : {n_projects:,}")
    print(f"  Files     : {n_files:,}")
    print(f"  Keywords  : {n_keywords:,}")
    print(f"  Persons   : {n_persons:,}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()