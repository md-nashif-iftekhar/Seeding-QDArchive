import os
import json
import time
import zipfile
from datetime import datetime
from pathlib import Path

import requests as req
from dotenv import load_dotenv

from config import DB_PATH, ARCHIVE_DIR, FILE_DELAY, REPOSITORIES
from db import init_db, get_projects_by_repo, insert_file, update_project

load_dotenv()

SIKT_USERNAME = os.getenv("SIKT_USERNAME", "")
SIKT_PASSWORD = os.getenv("SIKT_PASSWORD", "")
REPO_NAME     = REPOSITORIES[20]["name"]
REPO_ID       = 20

SKIP_EXTENSIONS = {".js", ".css", ".ico", ".woff", ".woff2"}

def login(page):
    from playwright.sync_api import TimeoutError as PWTimeout

    print("  Logging in to Surveybanken…")
    page.goto(
        "https://surveybanken.sikt.no/en/study/"
        "ca53363c-6fc3-498a-a2fb-0a732322ee22/7",
        wait_until="networkidle", timeout=30000
    )
    page.wait_for_timeout(2000)

    page.click("text=Log in")
    page.wait_for_load_state("networkidle", timeout=15000)
    page.wait_for_timeout(1500)

    try:
        page.wait_for_selector("text=Logg inn med brukernavn/passord", timeout=5000)
        page.click("text=Logg inn med brukernavn/passord")
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_timeout(1500)
    except PWTimeout:
        pass

    page.fill("input[type='text']", SIKT_USERNAME)
    page.fill("input[type='password']", SIKT_PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_load_state("networkidle", timeout=20000)
    page.wait_for_timeout(2000)

    content = page.content().lower()
    ok = any(kw in content for kw in ["log out", "logout", "logg ut"])
    print(f"  Login: {'SUCCESS' if ok else 'FAILED'}")
    return ok



def assert_step(condition: bool, message: str):
    """Print assertion result."""
    status = "Ok" if condition else "Not Ok"
    print(f"    [{status}] {message}")
    return condition



def download_study(page, row: dict, folder: Path) -> str:
    from playwright.sync_api import TimeoutError as PWTimeout

    project_url = row["project_url"] or ""
    if not project_url:
        return "FAILED_SERVER_UNRESPONSIVE"

    existing = list(folder.glob("*.zip")) + list(folder.glob("*.csv")) + \
               list(folder.glob("*.sav")) + list(folder.glob("*.pdf"))
    if existing:
        return "SUCCEEDED"

    try:
        print(f"    Navigating to: {project_url[:70]}")
        page.goto(project_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        zip_links = page.evaluate("""
            () => Array.from(document.querySelectorAll('a'))
                       .map(a => a.href)
                       .filter(h => h.includes('nsd.no/data'))
        """)

        assert_step(True, f"Direct links found: {len(zip_links)}")

        for href in zip_links:
            if href:
                print(f"    Trying direct: {href[-50:]}")
                try:
                    cookies = page.context.cookies()
                    jar = {c["name"]: c["value"] for c in cookies}
                    resp = req.get(href, cookies=jar, timeout=60, stream=True,
                                   headers={"User-Agent": "Mozilla/5.0"})
                    assert_step(resp.status_code == 200,
                                f"HTTP {resp.status_code} for direct link")
                    if resp.status_code == 200:
                        folder.mkdir(parents=True, exist_ok=True)
                        fname = href.split("/")[-1] or "data.zip"
                        fpath = folder / fname
                        total = 0
                        with open(fpath, "wb") as f:
                            for chunk in resp.iter_content(65536):
                                f.write(chunk)
                                total += len(chunk)
                        if assert_step(total > 500, f"File size: {total/1e3:.1f} KB"):
                            print(f"    [OK] {fname}")
                            return "SUCCEEDED"
                        else:
                            fpath.unlink()
                except Exception as e:
                    assert_step(False, f"Direct link error: {e}")

        dl_btn = None
        for sel in ["text=Download data", "button:has-text('Download data')"]:
            el = page.query_selector(sel)
            if el and el.is_visible():
                dl_btn = el
                break

        if not assert_step(dl_btn is not None, "Download data button found"):
            return "FAILED_LOGIN_REQUIRED"

        page.wait_for_timeout(1000)
        dl_btn.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        dl_btn.click()
        page.wait_for_timeout(3000)

        modal = page.query_selector("[role='dialog'], .modal, #modal, [aria-modal='true']")
        comboboxes = page.query_selector_all("input[role='combobox']")
        visible_cbs = [el for el in comboboxes if el.is_visible()]

        modal_open = modal is not None or len(visible_cbs) > 0
        assert_step(modal_open, f"Modal opened (comboboxes: {len(visible_cbs)})")

        if not modal_open:
            dl_btn.click()
            page.wait_for_timeout(3000)
            visible_cbs = [el for el in page.query_selector_all("input[role='combobox']")
                          if el.is_visible()]
            assert_step(len(visible_cbs) > 0, f"Modal opened on retry (comboboxes: {len(visible_cbs)})")

        visible_cbs = [el for el in page.query_selector_all("input[role='combobox']")
                      if el.is_visible()]

        if assert_step(len(visible_cbs) >= 1, f"Purpose combobox found ({len(visible_cbs)} total)"):
            purpose_cb = visible_cbs[0]
            purpose_cb.click()
            page.wait_for_timeout(800)
            purpose_cb.fill("Other")
            page.wait_for_timeout(500)

            other_opt = page.query_selector("[role='option']:has-text('Other')")
            if assert_step(other_opt is not None, "Other option found in dropdown"):
                other_opt.click()
                page.wait_for_timeout(500)
            else:
                page.keyboard.press("Enter")
                page.wait_for_timeout(500)

        page.wait_for_timeout(200)  # dropdown closed by clicking option
        page.wait_for_timeout(500)

        visible_cbs = [el for el in page.query_selector_all("input[role='combobox']")
                      if el.is_visible()]

        if assert_step(len(visible_cbs) >= 2, f"Institution combobox found"):
            inst_cb = visible_cbs[1]
            inst_cb.click()
            page.wait_for_timeout(800)
            inst_cb.fill("Friedrich-Alexander")
            page.wait_for_timeout(1000)

            opts = page.query_selector_all("[role='option']")
            visible_opts = [o for o in opts if o.is_visible()]
            if assert_step(len(visible_opts) > 0, f"Institution options found: {len(visible_opts)}"):
                visible_opts[0].click()
                page.wait_for_timeout(500)
                print(f"    Institution: {visible_opts[0].inner_text().strip()[:50]}")
            else:
                page.wait_for_timeout(200)  # dropdown closed by clicking option
                page.wait_for_timeout(300)
                enter_link = page.query_selector("text=Enter the name of your institution here")
                if assert_step(enter_link is not None, "Enter institution link found"):
                    enter_link.click()
                    page.wait_for_timeout(500)
                    text_inp = page.query_selector("input[type='text']:not([role='combobox'])")
                    if text_inp and text_inp.is_visible():
                        text_inp.fill("FAU Erlangen-Nuernberg")
                        page.wait_for_timeout(300)
                        print(f"    Institution: manual entry")
        else:
            print(f"    [INFO] No institution field")

        page.wait_for_timeout(200)  # dropdown closed by clicking option
        page.wait_for_timeout(500)

        result = page.evaluate("""
            () => {
                const cbs = document.querySelectorAll('input[type="checkbox"]');
                let clicked = 0;
                cbs.forEach(cb => { if (!cb.checked) { cb.click(); clicked++; } });
                return {total: cbs.length, clicked: clicked};
            }
        """)
        assert_step(result["total"] > 0,
                    f"Checkboxes: {result['total']} found, {result['clicked']} clicked")
        page.wait_for_timeout(500)

        page.screenshot(path="debug_after_form.png")
        print(f"    Screenshot: debug_after_form.png")

        page.wait_for_timeout(1500)
        folder.mkdir(parents=True, exist_ok=True)

        for fmt in ["CSV", "SPSS", "STATA"]:
            fmt_el = None
            for sel in [
                f"button:has-text('{fmt}')",
                f"a:has-text('{fmt}')",
                f"[role='button']:has-text('{fmt}')",
            ]:
                el = page.query_selector(sel)
                if el:
                    fmt_el = el
                    disabled = el.get_attribute("disabled")
                    enabled  = el.is_enabled()
                    assert_step(True, f"{fmt} element: disabled={disabled!r} enabled={enabled}")
                    break

            if not assert_step(fmt_el is not None, f"{fmt} element found"):
                continue

            try:
                with page.expect_download(timeout=60000) as dl_info:
                    fmt_el.click(force=True)
                dl   = dl_info.value
                name = dl.suggested_filename or f"data.{fmt.lower()}"
                dl.save_as(str(folder / name))
                size = (folder / name).stat().st_size
                if assert_step(size > 100, f"{fmt} download: {size/1e3:.1f} KB"):
                    print(f"    [OK] {name}")
                    return "SUCCEEDED"
                else:
                    (folder / name).unlink()
            except Exception as e:
                assert_step(False, f"{fmt} download failed: {e}")
                continue

        return "FAILED_SERVER_UNRESPONSIVE"

    except Exception as e:
        print(f"    [ERROR] {e}")
        return "FAILED_SERVER_UNRESPONSIVE"

def record_files(conn, pid: int, folder: Path):
    """Record downloaded files in DB, extracting ZIPs first."""
    for f in list(folder.iterdir()):
        if f.is_file() and f.name != "_metadata.json":
            ext = f.suffix.lower()
            if ext in SKIP_EXTENSIONS:
                continue
            if ext == ".zip":
                try:
                    with zipfile.ZipFile(f, "r") as zf:
                        zf.extractall(folder)
                        print(f"    Extracted {len(zf.namelist())} files from {f.name}")
                    for info in zipfile.ZipFile(f).infolist():
                        fname = info.filename
                        if fname.endswith("/"): continue
                        fext = Path(fname).suffix.lower()
                        if fext in SKIP_EXTENSIONS: continue
                        insert_file(conn, pid,
                                    file_name=Path(fname).name,
                                    file_type=fext.lstrip(".") or "unknown",
                                    status="SUCCEEDED")
                    continue
                except Exception as e:
                    print(f"    Extract failed: {e}")
            insert_file(conn, pid,
                        file_name=f.name,
                        file_type=ext.lstrip(".") or "unknown",
                        status="SUCCEEDED")



def main():
    if not SIKT_USERNAME or not SIKT_PASSWORD:
        print("[ERROR] Set SIKT_USERNAME and SIKT_PASSWORD in .env")
        return
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] '{DB_PATH}' not found.")
        return

    print("=" * 60)
    print("QDArchive — Sikt Playwright Downloader")
    print("=" * 60)
    print(f"  Username: {SIKT_USERNAME}")
    print("=" * 60)

    from playwright.sync_api import sync_playwright

    conn = init_db(DB_PATH)
    rows = get_projects_by_repo(conn, REPO_ID)

    seen, dedup = set(), []
    for r in rows:
        uid = r["project_url"] or ""
        if uid and uid not in seen:
            seen.add(uid)
            dedup.append(r)
    rows = dedup
    print(f"\n  Total Sikt studies: {len(rows)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        context = browser.new_context(accept_downloads=True)
        page    = context.new_page()

        if not login(page):
            print("[ERROR] Login failed")
            browser.close()
            conn.close()
            return

        ok = fail = skip = 0

        for i, row in enumerate(rows, 1):
            pid   = row["id"]
            title = row["title"]
            uid   = row["download_project_folder"] or str(pid)

            n_ok = conn.execute(
                "SELECT COUNT(*) FROM files WHERE project_id=? AND status='SUCCEEDED'",
                (pid,)
            ).fetchone()[0]
            if n_ok > 0:
                skip += 1
                continue

            conn.execute(
                "DELETE FROM files WHERE project_id=? AND status!='SUCCEEDED'", (pid,)
            )
            conn.commit()

            folder = Path(ARCHIVE_DIR) / REPO_NAME / uid
            folder.mkdir(parents=True, exist_ok=True)

            meta = folder / "_metadata.json"
            if not meta.exists():
                with open(meta, "w", encoding="utf-8") as f:
                    json.dump(dict(row), f, indent=2, default=str)

            print(f"\n  [{i}/{len(rows)}] {title[:55]}")

            status = download_study(page, row, folder)

            if status == "SUCCEEDED":
                record_files(conn, pid, folder)
                ok += 1
            else:
                link = folder / "catalogue_link.txt"
                if not link.exists():
                    with open(link, "w", encoding="utf-8") as f:
                        f.write(f"Title      : {title}\n")
                        f.write(f"Project URL: {row['project_url']}\n")
                        f.write(f"Status     : {status}\n")
                insert_file(conn, pid, file_name=f"{uid}.zip",
                            file_type="zip", status=status)
                fail += 1

            update_project(conn, pid, {
                "download_date": datetime.utcnow().isoformat()
            })
            time.sleep(FILE_DELAY)

        browser.close()
        conn.close()

    print(f"\n{'='*60}")
    print(f"Done — succeeded: {ok}  failed: {fail}  skipped: {skip}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()