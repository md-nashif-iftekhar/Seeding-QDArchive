import re
import sqlite3
import xml.etree.ElementTree as ET

import requests

from search.base import BaseSearcher
from db import insert_project, insert_keywords, insert_persons, project_exists
from config import SIKT_OAI_URL, SIKT_SET, SIKT_MAX_RECORDS, REPOSITORIES, HEADERS

# Repository config
REPO      = REPOSITORIES[20]
REPO_ID   = 20
REPO_URL  = REPO["url"]
REPO_NAME = REPO["name"]
METHOD    = REPO["method"]

# Sikt study catalogue base URL
SIKT_CATALOGUE = "https://sikt.no/en/find-data"

# XML namespaces
NS = {
    "oai":    "http://www.openarchives.org/OAI/2.0/",
    "dc":     "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}

# Keywords indicating qualitative research
QUALITATIVE_KEYWORDS = [
    "qualitative", "interview", "focus group",
    "ethnograph", "narrative", "discourse",
    "thematic", "grounded theory", "observation",
    "case study", "oral history", "fieldnote",
    "field note", "transcript",
]


class SiktSearcher(BaseSearcher):

    name    = "Sikt"
    OAI_URL = SIKT_OAI_URL

    def search(self, conn: sqlite3.Connection, queries: list[str]):

        print(f"\n[{self.name}] Starting CESSDA OAI-PMH harvest…")
        print(f"  Repository ID : {REPO_ID}")
        print(f"  Note: SIKT set removed from CESSDA — harvesting all and filtering by publisher")
        print(f"  Note: Files require data access agreement — metadata only.")

        saved      = 0
        resumption = None
        total_seen = 0

        while total_seen < SIKT_MAX_RECORDS:
            xml_data = self._fetch_oai_page(resumption)
            if xml_data is None:
                break

            try:
                root = ET.fromstring(xml_data)
            except ET.ParseError as e:
                self.log(f"[ERROR] XML parse error: {e}")
                break

            error_el = root.find(".//oai:error", NS)
            if error_el is not None:
                self.log(f"[ERROR] OAI-PMH error: {error_el.text}")
                break

            for record in root.findall(".//oai:record", NS):
                parsed = self._parse_record(record)
                if parsed and self._is_qualitative(parsed):
                    project_id = self._save_record(conn, parsed)
                    if project_id:
                        saved += 1
                total_seen += 1

            # OAI-PMH pagination token
            token_el = root.find(".//oai:resumptionToken", NS)
            if token_el is not None and token_el.text:
                resumption = token_el.text
                self.log(
                    f"  Harvested {total_seen} records, "
                    f"{saved} qualitative saved. Continuing…"
                )
                self.polite_sleep()
            else:
                break

        print(f"[{self.name}] Done — {saved} qualitative projects saved.\n")

    def _fetch_oai_page(self, resumption_token: str = None) -> str | None:
        """Fetch one CESSDA OAI-PMH page as raw XML string."""
        if resumption_token:
            params = {"verb": "ListRecords", "resumptionToken": resumption_token}
        else:
            params = {
                "verb":           "ListRecords",
                "metadataPrefix": "oai_dc",
            }
        try:
            resp = requests.get(
                self.OAI_URL, params=params,
                headers=HEADERS, timeout=30,
            )
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            self.log(f"[ERROR] OAI-PMH fetch failed: {e}")
            return None

    def _parse_record(self, record: ET.Element) -> dict | None:
        try:
            header = record.find("oai:header", NS)
            if header is None:
                return None
            if header.get("status", "") == "deleted":
                return None

            identifier_el = header.find("oai:identifier", NS)
            oai_id        = identifier_el.text.strip() if identifier_el is not None else ""

            nsd_match = re.search(r"NSD\d+", oai_id, re.IGNORECASE)
            nsd_id    = nsd_match.group(0).upper() if nsd_match else ""

            metadata = record.find(".//oai_dc:dc", NS)
            if metadata is None:
                return None

            def get(tag: str) -> str:
                el = metadata.find(f"dc:{tag}", NS)
                return el.text.strip() if el is not None and el.text else ""

            def get_all(tag: str) -> list[str]:
                return [
                    el.text.strip()
                    for el in metadata.findall(f"dc:{tag}", NS)
                    if el.text and el.text.strip()
                ]

            publishers  = get_all("publisher")
            pub_text    = " ".join(publishers).lower()
            is_sikt     = (
                nsd_id != ""  # has NSD ID in OAI identifier
                or any(kw in pub_text for kw in ["sikt", "nsd", "norsk", "norwegian"])
                or "nsd" in oai_id.lower()
                or "sikt" in oai_id.lower()
            )
            if not is_sikt:
                return None

            title       = get("title")
            description = get("description")
            rights      = get("rights")
            date        = get("date")
            language    = get("language")
            creators    = get_all("creator")
            subjects    = get_all("subject")

            doi = ""
            for id_el in metadata.findall("dc:identifier", NS):
                val = (id_el.text or "").strip()
                if "doi.org" in val or val.startswith("10."):
                    doi = val if val.startswith("http") else f"https://doi.org/{val}"
                    break

            project_url = (
                f"https://surveybanken.sikt.no/study/{nsd_id}"
                if nsd_id
                else get("identifier")
                or f"{SIKT_CATALOGUE}?id={oai_id}"
            )

            if not title:
                return None

            return {
                "nsd_id":      nsd_id,
                "oai_id":      oai_id,
                "title":       title,
                "description": description,
                "rights":      rights,
                "date":        date,
                "language":    language,
                "doi":         doi,
                "creators":    creators,
                "subjects":    subjects,
                "project_url": project_url,
            }

        except Exception as e:
            self.log(f"[WARN] Could not parse record: {e}")
            return None

    def _save_record(self, conn: sqlite3.Connection,
                     parsed: dict) -> int | None:
        """Insert a parsed Sikt record into the database."""

        if project_exists(conn, parsed["project_url"]):
            return None

        project_id = insert_project(conn, {
            "query_string":               None,   # OAI-PMH harvest, no query
            "repository_id":              REPO_ID,
            "repository_url":             REPO_URL,
            "project_url":                parsed["project_url"],
            "version":                    None,
            "title":                      parsed["title"],
            "description":                (parsed["description"] or "")[:500],
            "language":                   parsed["language"] or None,
            "doi":                        parsed["doi"] or None,
            "upload_date":                parsed["date"] or None,
            "download_repository_folder": REPO_NAME,
            "download_project_folder":    parsed["nsd_id"] or None,
            "download_version_folder":    None,
            "download_method":            METHOD,
            "license":                    parsed["rights"] or None,
            "license_url":                None,
        })

        if not project_id:
            return None

        insert_keywords(conn, project_id, parsed["subjects"])

        persons = [
            {"name": name, "role": "UNKNOWN"}
            for name in parsed["creators"]
        ]
        insert_persons(conn, project_id, persons)

        return project_id

    def _is_qualitative(self, parsed: dict) -> bool:
        """Return True if the record appears to be qualitative research."""
        text = (
            (parsed.get("title") or "") + " " +
            (parsed.get("description") or "") + " " +
            " ".join(parsed.get("subjects") or [])
        ).lower()
        return any(kw in text for kw in QUALITATIVE_KEYWORDS)