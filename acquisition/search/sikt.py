import sqlite3
import xml.etree.ElementTree as ET

from search.base import BaseSearcher
from db import insert_project
from config import SIKT_OAI_URL, SIKT_SET, SIKT_MAX_RECORDS

# XML namespaces
NS = {
    "oai":    "http://www.openarchives.org/OAI/2.0/",
    "dc":     "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}


class SiktSearcher(BaseSearcher):

    name    = "Sikt"
    OAI_URL = SIKT_OAI_URL

    def search(self, conn: sqlite3.Connection, queries: list[str]):
        print(f"\n[{self.name}] Starting OAI-PMH harvest from CESSDA (set=SIKT)…")
        print(f"  Note: Sikt files require data access agreement — collecting metadata only.")

        saved      = 0
        resumption = None
        total_seen = 0

        while total_seen < SIKT_MAX_RECORDS:
            xml_data = self._fetch_records(resumption)
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

            # Pagination
            token_el = root.find(".//oai:resumptionToken", NS)
            if token_el is not None and token_el.text:
                resumption = token_el.text
                self.log(f"  Harvested {total_seen} records, {saved} saved. Continuing…")
                self.polite_sleep()
            else:
                break

        print(f"[{self.name}] Done — {saved} qualitative projects saved.\n")

    def _fetch_records(self, resumption_token: str = None) -> str | None:
        """Fetch one OAI-PMH page as raw XML."""
        if resumption_token:
            params = {
                "verb":            "ListRecords",
                "resumptionToken": resumption_token,
            }
        else:
            params = {
                "verb":           "ListRecords",
                "metadataPrefix": "oai_dc",
                "set":            SIKT_SET,
            }

        try:
            import requests
            resp = requests.get(
                self.OAI_URL, params=params,
                headers={"User-Agent": "QDArchive-Seeder/1.0 (FAU Erlangen)"},
                timeout=30,
            )
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
                return [el.text.strip() for el in metadata.findall(f"dc:{tag}", NS) if el.text]

            title       = get("title")
            description = get("description")
            license_str = get("rights")
            source_link = get("identifier") or f"https://sikt.no/en/find-data?id={identifier}"
            date        = get("date")
            creators    = get_all("creator")
            subjects    = get_all("subject")

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
                "download_url":      source_link,
                "raw_metadata":      str({
                    "identifier": identifier,
                    "title":      title,
                    "subjects":   subjects,
                })[:2000],
            }
        except Exception as e:
            self.log(f"[WARN] Could not parse record: {e}")
            return None

    def _is_qualitative(self, record: dict) -> bool:
        """Filter for qualitative research records."""
        qualitative_keywords = [
            "qualitative", "interview", "focus group",
            "ethnograph", "narrative", "discourse",
            "thematic", "grounded theory", "observation",
        ]
        text = (
            (record.get("title") or "") + " " +
            (record.get("description") or "") + " " +
            (record.get("keywords") or "")
        ).lower()

        return any(kw in text for kw in qualitative_keywords)