import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from dotenv import load_dotenv

from search.base import BaseSearcher
from db import insert_project, update_project
from config import (
    FSD_OAI_URL, FSD_MAX_RECORDS,
    ARCHIVE_DIR, FILE_DELAY, QDA_EXTENSIONS,
)
load_dotenv()

NS = {
    "oai":    "http://www.openarchives.org/OAI/2.0/",
    "dc":     "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}

# FSD base URLs
FSD_BASE_URL     = "https://services.fsd.tuni.fi"
FSD_LOGIN_URL    = f"{FSD_BASE_URL}/Shibboleth.sso/Login"
FSD_DOWNLOAD_URL = f"{FSD_BASE_URL}/v0/download"
FSD_CATALOGUE    = f"{FSD_BASE_URL}/catalogue/study"


class FSDSearcher(BaseSearcher):

    name    = "FSD"
    OAI_URL = FSD_OAI_URL

    def __init__(self):
        self.session     = requests.Session()
        self.session.headers.update({
            "User-Agent": "QDArchive-Seeder/1.0 (FAU Erlangen)"
        })
        self.authenticated = False
        self.username      = os.getenv("FSD_USERNAME")
        self.password      = os.getenv("FSD_PASSWORD")


    def login(self) -> bool:
        if not self.username or not self.password:
            self.log("[WARN] No credentials found in .env — download will be limited to metadata only.")
            return False

        try:
            resp = self.session.get(
                f"{FSD_BASE_URL}/profile/login",
                timeout=30,
            )
            resp.raise_for_status()

            csrf_match = re.search(
                r'name=["\']_csrf["\'].*?value=["\']([^"\']+)["\']',
                resp.text
            )
            csrf_token = csrf_match.group(1) if csrf_match else ""

            login_resp = self.session.post(
                f"{FSD_BASE_URL}/profile/login",
                data={
                    "username":  self.username,
                    "password":  self.password,
                    "_csrf":     csrf_token,
                },
                timeout=30,
                allow_redirects=True,
            )

            if "logout" in login_resp.text.lower() or login_resp.status_code == 200:
                self.authenticated = True
                self.log("Login successful ✅")
                return True
            else:
                self.log("[WARN] Login may have failed — check credentials in .env")
                return False

        except Exception as e:
            self.log(f"[ERROR] Login failed: {e}")
            return False
        
    def search(self, conn: sqlite3.Connection, queries: list[str]):
        print(f"\n[{self.name}] Starting OAI-PMH metadata harvest…")

        # Attempt login for download capability
        self.login()

        saved      = 0
        resumption = None
        total_seen = 0

        while total_seen < FSD_MAX_RECORDS:
            xml_data = self._fetch_oai_page(resumption)
            if xml_data is None:
                break

            try:
                root = ET.fromstring(xml_data)
            except ET.ParseError as e:
                self.log(f"[ERROR] XML parse error: {e}")
                break

            for record in root.findall(".//oai:record", NS):
                record_data = self._parse_record(record)
                if record_data and self._is_qualitative(record_data):
                    if insert_project(conn, record_data):
                        saved += 1
                total_seen += 1

            # OAI-PMH pagination token
            token_el = root.find(".//oai:resumptionToken", NS)
            if token_el is not None and token_el.text:
                resumption = token_el.text
                self.log(f"Harvested {total_seen} records, {saved} qualitative saved…")
                self.polite_sleep()
            else:
                break

        print(f"[{self.name}] Metadata harvest done — {saved} qualitative projects saved.\n")

    def _fetch_oai_page(self, resumption_token: str = None) -> str | None:
        """Fetch one OAI-PMH page as raw XML."""
        params = (
            {"verb": "ListRecords", "resumptionToken": resumption_token}
            if resumption_token
            else {"verb": "ListRecords", "metadataPrefix": "oai_dc"}
        )
        try:
            resp = self.session.get(self.OAI_URL, params=params, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            self.log(f"[ERROR] OAI-PMH fetch failed: {e}")
            return None

    def _parse_record(self, record: ET.Element) -> dict | None:
        """Parse one OAI-PMH record into a flat dict."""
        try:
            header     = record.find("oai:header", NS)
            identifier = header.find("oai:identifier", NS).text if header is not None else ""

            metadata = record.find(".//oai_dc:dc", NS)
            if metadata is None:
                return None

            def get(tag):
                el = metadata.find(f"dc:{tag}", NS)
                return el.text.strip() if el is not None and el.text else ""

            def get_all(tag):
                return [
                    el.text.strip()
                    for el in metadata.findall(f"dc:{tag}", NS)
                    if el.text
                ]

            title       = get("title")
            description = get("description")
            license_str = get("rights")
            date        = get("date")
            creators    = get_all("creator")
            subjects    = get_all("subject")

            # Extract FSD study ID from identifier (e.g. "FSD3522")
            fsd_id_match = re.search(r"FSD\d+", identifier)
            fsd_id       = fsd_id_match.group(0) if fsd_id_match else ""

            source_link = (
                f"{FSD_CATALOGUE}/{fsd_id}"
                if fsd_id
                else get("identifier")
                or f"{self.OAI_URL}?verb=GetRecord&identifier={identifier}&metadataPrefix=oai_dc"
            )

            # Detect access condition (A/B/C/D) from rights field
            condition = self._detect_condition(license_str)

            if not title:
                return None

            return {
                "source":            self.name,
                "source_link":       source_link,
                "title":             title,
                "description":       description[:500],
                "license":           license_str,
                "license_url":       "",
                "authors":           str(creators),
                "keywords":          str(subjects),
                "publication_date":  date,
                "has_qda_files":     0,
                "qda_file_types":    "[]",
                "has_primary_data":  0,
                "file_count":        None,
                "download_url":      f"{FSD_DOWNLOAD_URL}/{fsd_id}" if fsd_id else source_link,
                "raw_metadata":      str({
                    "identifier": identifier,
                    "fsd_id":     fsd_id,
                    "condition":  condition,
                    "title":      title,
                    "subjects":   subjects,
                })[:2000],
            }
        except Exception as e:
            self.log(f"[WARN] Could not parse record: {e}")
            return None

    def download_files(self, conn: sqlite3.Connection):
        from db import get_by_source
        import time, json

        rows = get_by_source(conn, self.name)
        self.log(f"Downloading files for {len(rows)} FSD projects…")

        for row in rows:
            raw   = row["raw_metadata"] or ""
            fsd_id    = ""
            condition = "B"

            try:
                meta      = eval(raw)   # stored as str(dict)
                fsd_id    = meta.get("fsd_id", "")
                condition = meta.get("condition", "B")
            except Exception:
                pass

            if not fsd_id:
                self.log(f"[SKIP] No FSD ID for: {row['title'][:50]}")
                continue

            if condition == "D":
                self.log(f"[SKIP] Condition D (depositor permission required): {fsd_id}")
                continue

            if condition in ("B", "C") and not self.authenticated:
                self.log(f"[SKIP] Condition {condition} requires login — not authenticated: {fsd_id}")
                continue

            # Create folder
            folder = Path(ARCHIVE_DIR) / "FSD" / f"{row['id']:04d}_{fsd_id}"
            folder.mkdir(parents=True, exist_ok=True)

            # Save metadata JSON
            meta_path = folder / "_metadata.json"
            if not meta_path.exists():
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(dict(row), f, indent=2, default=str)

            # Download ZIP
            zip_path = folder / f"{fsd_id}.zip"
            if zip_path.exists():
                self.log(f"[SKIP] Already downloaded: {fsd_id}")
                continue

            try:
                self.log(f"Downloading {fsd_id} (Condition {condition})…")
                resp = self.session.get(
                    f"{FSD_DOWNLOAD_URL}/{fsd_id}",
                    timeout=120,
                    stream=True,
                )

                if resp.status_code == 401:
                    self.log(f"[SKIP] HTTP 401 — not authorised for {fsd_id}")
                    continue
                elif resp.status_code == 403:
                    self.log(f"[SKIP] HTTP 403 — access denied for {fsd_id}")
                    continue

                resp.raise_for_status()

                total = 0
                with open(zip_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        f.write(chunk)
                        total += len(chunk)

                self.log(f"[OK] {fsd_id}.zip  ({total/1e3:.1f} KB)")
                update_project(conn, row["id"], {
                    "has_primary_data": 1,
                    "file_count":       1,
                })

            except Exception as e:
                self.log(f"[ERROR] {fsd_id}: {e}")

            time.sleep(FILE_DELAY)

    def _detect_condition(self, rights_str: str) -> str:
        """Detect FSD access condition A/B/C/D from rights field."""
        lower = (rights_str or "").lower()
        if "condition a" in lower or "freely available" in lower or "cc by" in lower:
            return "A"
        elif "condition b" in lower:
            return "B"
        elif "condition c" in lower:
            return "C"
        elif "condition d" in lower:
            return "D"
        return "B"

    def _is_qualitative(self, record: dict) -> bool:
        qualitative_keywords = [
            "qualitative", "interview", "haastattel",
            "focus group", "ethnograph", "narrative",
            "discourse", "thematic", "grounded theory",
            "observation", "case study",
        ]
        text = (
            (record.get("title") or "") + " " +
            (record.get("description") or "") + " " +
            (record.get("keywords") or "")
        ).lower()
        return any(kw in text for kw in qualitative_keywords)