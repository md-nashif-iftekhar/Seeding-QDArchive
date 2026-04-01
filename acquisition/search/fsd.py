import re
import sqlite3
import xml.etree.ElementTree as ET

import requests

from search.base import BaseSearcher
from db import insert_project, insert_keywords, insert_persons, project_exists
from config import FSD_OAI_URL, FSD_MAX_RECORDS, REPOSITORIES, HEADERS

REPO      = REPOSITORIES[11]
REPO_ID   = 11
REPO_URL  = REPO["url"]
REPO_NAME = REPO["name"]
METHOD    = REPO["method"]

FSD_CATALOGUE    = "https://services.fsd.tuni.fi/catalogue"
FSD_DOWNLOAD_URL = "https://services.fsd.tuni.fi/v0/download"

NS = {
    "oai":    "http://www.openarchives.org/OAI/2.0/",
    "dc":     "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
}

_CONDITION_A_IDS_CACHE: set | None = None

QUALITATIVE_KEYWORDS = [
    # English
    "qualitative", "interview", "focus group",
    "ethnograph", "narrative", "discourse",
    "thematic", "grounded theory", "observation",
    "case study", "oral history", "fieldnote",
    "field note", "transcript", "writing competition",
    "diary", "diaries", "essay", "memoir",
    # Finnish
    "haastattel",        # interview / haastattelututkimus
    "laadullinen",       # qualitative
    "havainnointi",      # observation
    "kenttätyö",         # fieldwork
    "tapaustutkimus",    # case study
    "fokusryhmä",        # focus group
    "narratiivi",        # narrative
    "kirjoitus",         # writing/text data
    "kirjoitelma",       # essay/written data
    "havaintomuistio",   # field notes
    "kirjoituskilpailu", # writing competition
    "muistelu",          # memoir/reminiscence
    "päiväkirja",        # diary
    "elämäntarina",      # life story
    "ryhmäkeskustelu",   # group discussion
]


def fetch_condition_a_ids() -> set:
    global _CONDITION_A_IDS_CACHE
    if _CONDITION_A_IDS_CACHE is not None:
        return _CONDITION_A_IDS_CACHE

    all_ids  = set()
    page     = 0
    per_page = 100

    print(f"  [FSD] Fetching Condition A IDs from catalogue…")

    while True:
        try:
            resp = requests.get(
                f"{FSD_CATALOGUE}/index",
                params={
                    "limit":                            per_page,
                    "lang":                             "en",
                    "page":                             page,
                    "field":                            "publishing_date",
                    "direction":                        "descending",
                    "dissemination_policy_string_facet": "A",
                    "data_kind_string_facet":           "Qualitative",
                },
                headers=HEADERS,
                timeout=30,
            )

            if resp.status_code != 200:
                print(f"  [FSD] Catalogue HTTP {resp.status_code} — stopping")
                break

            ids_on_page = set(re.findall(r"/catalogue/(FSD\d+)", resp.text))
            new_ids     = ids_on_page - all_ids

            if not new_ids:
                break

            all_ids.update(new_ids)
            page += 1

            if len(ids_on_page) < per_page // 2:
                break

        except Exception as e:
            print(f"  [FSD] Catalogue fetch failed: {e}")
            break

    print(f"  [FSD] Found {len(all_ids)} Condition A qualitative datasets")
    _CONDITION_A_IDS_CACHE = all_ids
    return all_ids


class FSDSearcher(BaseSearcher):

    name    = "FSD"
    OAI_URL = FSD_OAI_URL

    def search(self, conn: sqlite3.Connection, queries: list[str]):
        print(f"\n[{self.name}] Starting OAI-PMH metadata harvest…")
        print(f"  Repository ID : {REPO_ID}")
        print(f"  Condition A   : fetched dynamically from catalogue")
        print(f"  Condition B/C : metadata + catalogue link only")

        condition_a = fetch_condition_a_ids()

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

            error_el = root.find(".//oai:error", NS)
            if error_el is not None:
                self.log(f"[ERROR] OAI-PMH error: {error_el.text}")
                break

            for record in root.findall(".//oai:record", NS):
                parsed = self._parse_record(record, condition_a)
                if parsed and self._is_qualitative(parsed):
                    project_id = self._save_record(conn, parsed)
                    if project_id:
                        saved += 1
                total_seen += 1

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
        params = (
            {"verb": "ListRecords", "resumptionToken": resumption_token}
            if resumption_token
            else {"verb": "ListRecords", "metadataPrefix": "oai_dc"}
        )
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

    def _parse_record(self, record: ET.Element,
                      condition_a: set) -> dict | None:
        try:
            header = record.find("oai:header", NS)
            if header is None:
                return None
            if header.get("status", "") == "deleted":
                return None

            identifier_el = header.find("oai:identifier", NS)
            oai_id        = identifier_el.text.strip() if identifier_el is not None else ""

            fsd_match = re.search(r"FSD\d+", oai_id)
            fsd_id    = fsd_match.group(0) if fsd_match else ""

            metadata = record.find(".//oai_dc:dc", NS)
            if metadata is None:
                return None

            def get_all(tag: str) -> list[str]:
                return [
                    el.text.strip()
                    for el in metadata.findall(f"dc:{tag}", NS)
                    if el.text and el.text.strip()
                ]

            titles       = get_all("title")
            descriptions = get_all("description")
            rights_list  = get_all("rights")
            subjects     = get_all("subject")
            creators     = get_all("creator")
            languages    = get_all("language")
            dates        = get_all("date")
            identifiers  = get_all("identifier")

            title = titles[1] if len(titles) > 1 else (titles[0] if titles else "")

            description = (
                descriptions[1] if len(descriptions) > 1
                else (descriptions[0] if descriptions else "")
            )

            rights = (
                rights_list[1] if len(rights_list) > 1
                else (rights_list[0] if rights_list else "")
            )

            condition = "A" if fsd_id in condition_a else "B"

            doi = ""
            for ident in identifiers:
                if ident.startswith("10."):
                    doi = f"https://doi.org/{ident}"
                    break
                elif "doi.org" in ident:
                    doi = ident
                    break

            project_url = f"{FSD_CATALOGUE}/{fsd_id}" if fsd_id else oai_id

            if not title:
                return None

            return {
                "fsd_id":      fsd_id,
                "oai_id":      oai_id,
                "title":       title,
                "description": description,
                "rights":      rights,
                "condition":   condition,
                "doi":         doi,
                "date":        dates[-1] if dates else "",
                "language":    ", ".join(languages),
                "creators":    creators,
                "subjects":    subjects,
                "project_url": project_url,
                "_all_titles": titles,
                "_all_descs":  descriptions,
                "_all_subj":   subjects,
            }

        except Exception as e:
            self.log(f"[WARN] Could not parse record: {e}")
            return None

    def _save_record(self, conn: sqlite3.Connection,
                     parsed: dict) -> int | None:
        if project_exists(conn, parsed["project_url"]):
            return None

        project_id = insert_project(conn, {
            "query_string":               None,
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
            "download_project_folder":    parsed["fsd_id"] or None,
            "download_version_folder":    None,
            "download_method":            METHOD,
            "license":                    parsed["rights"] or None,
            "license_url":                None,
        })

        if not project_id:
            return None

        insert_keywords(conn, project_id, parsed["subjects"])
        insert_persons(conn, project_id, [
            {"name": name, "role": "UNKNOWN"}
            for name in parsed["creators"]
        ])

        return project_id

    @staticmethod
    def try_condition_a_download(fsd_id: str, dest_folder) -> str:
        from pathlib import Path

        if not fsd_id:
            return "FAILED_SERVER_UNRESPONSIVE"

        zip_path = Path(dest_folder) / f"{fsd_id}.zip"
        if zip_path.exists():
            return "SUCCEEDED"

        url = f"{FSD_DOWNLOAD_URL}/{fsd_id}"

        try:
            resp = requests.get(
                url, headers=HEADERS,
                timeout=120, stream=True, allow_redirects=True,
            )

            if resp.status_code in (401, 403):
                return "FAILED_LOGIN_REQUIRED"
            if resp.status_code == 404:
                return "FAILED_SERVER_UNRESPONSIVE"
            if resp.status_code >= 500:
                return "FAILED_SERVER_UNRESPONSIVE"

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" in content_type:
                return "FAILED_LOGIN_REQUIRED"

            resp.raise_for_status()

            Path(dest_folder).mkdir(parents=True, exist_ok=True)
            total = 0
            with open(zip_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    total += len(chunk)

            print(f"      [OK]     {fsd_id}.zip  ({total/1e3:.1f} KB)")
            return "SUCCEEDED"

        except requests.exceptions.Timeout:
            return "FAILED_SERVER_UNRESPONSIVE"
        except Exception as e:
            print(f"      [ERROR]  {fsd_id}: {e}")
            return "FAILED_SERVER_UNRESPONSIVE"

    def _is_qualitative(self, parsed: dict) -> bool:

        if parsed.get("condition") == "A":
            return True

        text = " ".join([
            *parsed.get("_all_titles", []),
            *parsed.get("_all_descs",  []),
            *parsed.get("_all_subj",   []),
        ]).lower()

        return any(kw in text for kw in QUALITATIVE_KEYWORDS)