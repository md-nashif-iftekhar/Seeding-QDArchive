import os
import json
import time
import zipfile
import argparse
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from config import DB_PATH, ARCHIVE_DIR, FILE_DELAY, REPOSITORIES
from db import init_db, get_projects_by_repo, insert_file, update_project

load_dotenv()

FSD_USERNAME = os.getenv("FSD_USERNAME", "")
FSD_PASSWORD = os.getenv("FSD_PASSWORD", "")
REPO_NAME    = REPOSITORIES[11]["name"]
REPO_ID      = 11

SKIP_EXTENSIONS = {".js", ".css", ".ico", ".woff", ".woff2"}


def _handle_discovery_page(page):
    """Click 'Kirjaudu tästä (Click to login)' on discovery page."""
    from playwright.sync_api import TimeoutError as PWTimeout
    print(f"  Discovery page: {page.title()}")
    for sel in [
        "text=Kirjaudu tästä",
        "text=Click to login",
        "a[href*='accounts.fsd.uta.fi']",
        "a[href*='accounts.fsd.tuni.fi']",
        "a[href*='entityID=https%253A%252F%252Faccounts']",
    ]:
        try:
            page.wait_for_selector(sel, timeout=3000)
            el = page.query_selector(sel)
            if el:
                print(f"  Clicking: {el.inner_text().strip()!r}")
                el.click()
                page.wait_for_load_state("domcontentloaded", timeout=15000)
                print(f"  → {page.url}")
                return
        except PWTimeout:
            continue
    print("  [WARN] Direct login link not found on discovery page")


def _fill_credentials(page):
    from playwright.sync_api import TimeoutError as PWTimeout
    for sel in ["input[name='j_username']", "input[name='username']",
                "input[type='text']", "#username"]:
        try:
            page.wait_for_selector(sel, timeout=5000)
            page.fill(sel, FSD_USERNAME)
            print(f"  Filled username ({sel})")
            break
        except PWTimeout:
            continue

    for sel in ["input[name='j_password']", "input[name='password']",
                "input[type='password']", "#password"]:
        try:
            page.fill(sel, FSD_PASSWORD)
            print(f"  Filled password ({sel})")
            break
        except Exception:
            continue

    for sel in ["button[type='submit']", "input[type='submit']"]:
        try:
            page.click(sel)
            print(f"  Submitted")
            page.wait_for_load_state("networkidle", timeout=15000)
            print(f"  → {page.url}")
            if "Information Release" in page.title() or "e1s3" in page.url:
                _handle_consent_page(page)
            return
        except Exception:
            continue
    print("  [WARN] Submit button not found")


def _handle_consent_page(page):
    from playwright.sync_api import TimeoutError as PWTimeout
    print(f"  Consent page: {page.title()}")

    buttons = page.query_selector_all("button, input[type='submit']")
    for b in buttons:
        text = b.inner_text().strip() or b.get_attribute("value") or ""
        name = b.get_attribute("name") or ""
        print(f"    Button: {text!r} name={name!r}")

    for sel in [
        "input[name='_eventId_proceed']",
        "button[name='_eventId_proceed']",
        "input[value='Accept']",
        "button:has-text('Accept')",
        "input[type='submit']",
    ]:
        try:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text().strip() or el.get_attribute("value") or ""
                print(f"  ✅ Clicking ACCEPT: {text!r} ({sel})")
                el.click()
                page.wait_for_load_state("networkidle", timeout=20000)
                print(f"  After accept URL: {page.url}")
                return
        except Exception:
            continue
    print("  [WARN] Accept button not found")

def login_and_download(fsd_rows: list, condition_a_ids: set,
                       conn) -> None:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        context = browser.new_context(accept_downloads=True)
        page    = context.new_page()

        page.on("response", lambda r: print(f"    → {r.status} {r.url[:80]}")
                if any(kw in r.url for kw in
                       ["fsd", "shibboleth", "accounts", "disco"])
                else None)

        page.goto(
            "https://services.fsd.tuni.fi/Shibboleth.sso/Login"
            "?target=https%3A%2F%2Fservices.fsd.tuni.fi%2F",
            wait_until="domcontentloaded", timeout=30000
        )
        print(f"  URL: {page.url}")

        if "disco" in page.url:
            print("\n  Step 2: Discovery page…")
            _handle_discovery_page(page)

        _fill_credentials(page)

        print(f"\n  Step 4: Waiting for services.fsd.tuni.fi…")
        try:
            page.wait_for_url("**/services.fsd.tuni.fi/**",
                               timeout=30000, wait_until="domcontentloaded")
        except PWTimeout:
            if "accounts.fsd" in page.url or "Information Release" in page.title():
                _handle_consent_page(page)
                try:
                    page.wait_for_url("**/services.fsd.tuni.fi/**",
                                       timeout=20000, wait_until="domcontentloaded")
                except PWTimeout:
                    pass

        print(f"  Final URL: {page.url}")
        logged_in = any(kw in page.content().lower()
                        for kw in ["log out", "logout", "kirjaudu ulos"])
        print(f"  Login: {'Ok SUCCESS' if logged_in else '  UNCLEAR'}")

        print(f"\n  Downloading {len(fsd_rows)} datasets…")

        for i, row in enumerate(fsd_rows, 1):
            pid       = row["id"]
            title     = row["title"]
            fsd_id    = row["download_project_folder"] or ""
            condition = "A" if fsd_id in condition_a_ids else "B"

            n_ok = conn.execute(
                "SELECT COUNT(*) FROM files "
                "WHERE project_id=? AND status='SUCCEEDED'",
                (pid,)
            ).fetchone()[0]
            if n_ok > 0:
                print(f"\n  [{i}/{len(fsd_rows)}] [SKIP] {title[:50]}")
                continue

            conn.execute(
                "DELETE FROM files WHERE project_id=? AND status!='SUCCEEDED'",
                (pid,)
            )
            conn.commit()

            folder = Path(ARCHIVE_DIR) / REPO_NAME / fsd_id
            folder.mkdir(parents=True, exist_ok=True)

            meta = folder / "_metadata.json"
            if not meta.exists():
                with open(meta, "w", encoding="utf-8") as f:
                    json.dump(dict(row), f, indent=2, default=str)

            print(f"\n  [{i}/{len(fsd_rows)}] [{condition}] {title[:55]}")

            if not fsd_id:
                continue

            zip_path = folder / f"{fsd_id}.zip"
            if zip_path.exists():
                print(f"    [SKIP] Already downloaded")
                _record_success(conn, pid, zip_path, folder)
                continue

            study_url = (f"https://services.fsd.tuni.fi/catalogue/{fsd_id}"
                         f"?tab=download&lang=en&study_language=fi")
            status = "FAILED_SERVER_UNRESPONSIVE"

            try:
                print(f"    Navigating to: {study_url}")
                page.goto(study_url, wait_until="networkidle", timeout=30000)
                print(f"    Title: {page.title()}")

                for sel in [
                    "a[href*='/catalogue/download']",
                    "a:has-text('Download data')",
                    "a:has-text('Lataa aineisto')",
                    "input[type='submit']",
                    "button[type='submit']",
                ]:
                    try:
                        el = page.query_selector(sel)
                        if el and el.is_visible():
                            text = el.inner_text().strip() or ""
                            href = el.get_attribute("href") or ""
                            if text in ["Suomeksi", "In English", "På svenska"]:
                                continue
                            print(f"    Clicking: {text!r} ({sel}) → {href}")
                            with page.expect_download(timeout=120000) as dl_info:
                                el.click()
                            dl   = dl_info.value
                            name = dl.suggested_filename
                            print(f"    Filename: {name}")
                            dl.save_as(str(zip_path))
                            size = zip_path.stat().st_size
                            if size < 1000:
                                print(f"    [FAIL] Too small ({size}B) — likely error page")
                                zip_path.unlink()
                            else:
                                print(f"    [OK] {fsd_id}.zip ({size/1e3:.1f} KB)")
                                status = "SUCCEEDED"
                                _record_success(conn, pid, zip_path, folder)
                            break
                    except Exception as e:
                        print(f"    {sel}: {e}")
                        continue

                if status != "SUCCEEDED":
                    print(f"    [FAIL] Download not triggered")

            except Exception as e:
                print(f"    [ERROR] {e}")

            if status != "SUCCEEDED":
                insert_file(conn, pid, file_name=f"{fsd_id}.zip",
                            file_type="zip", status=status)
                _save_catalogue_link(folder, row)

            update_project(conn, pid, {
                "download_date": datetime.utcnow().isoformat()
            })
            time.sleep(FILE_DELAY)

        browser.close()
        print("\n  Browser closed.")


def _record_success(conn, pid: int, zip_path: Path, folder: Path):
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(folder)
            for info in zf.infolist():
                fname = info.filename
                ext   = Path(fname).suffix.lower()
                if fname.endswith("/"): continue
                if ext in SKIP_EXTENSIONS: continue
                if "/html/" in fname.lower(): continue
                if "/img/" in fname.lower(): continue
                insert_file(conn, pid,
                            file_name=Path(fname).name,
                            file_type=ext.lstrip(".") or "unknown",
                            status="SUCCEEDED")
        print(f"    Extracted files recorded in DB")
    except Exception as e:
        print(f"    [ERROR] Extract: {e}")
        insert_file(conn, pid, file_name=zip_path.name,
                    file_type="zip", status="SUCCEEDED")


def _save_catalogue_link(folder: Path, row):
    link = folder / "catalogue_link.txt"
    if not link.exists():
        with open(link, "w", encoding="utf-8") as f:
            f.write(f"Title      : {row['title']}\n")
            f.write(f"Project URL: {row['project_url']}\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-a", action="store_true")
    parser.add_argument("--only-b", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] '{DB_PATH}' not found.")
        return
    if not FSD_USERNAME or not FSD_PASSWORD:
        print("[ERROR] Set FSD_USERNAME and FSD_PASSWORD in .env")
        return

    print("="*60)
    print("QDArchive — FSD Playwright Downloader")
    print("="*60)
    print(f"  Username : {FSD_USERNAME}")
    print("="*60)

    from search.fsd import fetch_condition_a_ids
    condition_a_ids = fetch_condition_a_ids()

    conn = init_db(DB_PATH)
    rows = get_projects_by_repo(conn, REPO_ID)

    # Deduplicate
    seen    = set()
    deduped = []
    for r in rows:
        fsd_id = r["download_project_folder"] or ""
        if fsd_id and fsd_id not in seen:
            seen.add(fsd_id)
            deduped.append(r)
    rows = deduped

    if args.only_a:
        rows = [r for r in rows
                if (r["download_project_folder"] or "") in condition_a_ids]
        print(f"\n  Condition A: {len(rows)} datasets")
    elif args.only_b:
        rows = [r for r in rows
                if (r["download_project_folder"] or "") not in condition_a_ids]
        print(f"\n  Condition B: {len(rows)} datasets")
    else:
        print(f"\n  All: {len(rows)} datasets")

    try:
        login_and_download(rows, condition_a_ids, conn)
    finally:
        conn.close()

    print("\n" + "="*60)
    print("Done!")
    print("="*60)


if __name__ == "__main__":
    main()