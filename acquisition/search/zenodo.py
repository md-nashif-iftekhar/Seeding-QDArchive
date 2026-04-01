import json
import sqlite3

from search.base import BaseSearcher
from db import (
    insert_project, insert_keywords, insert_persons, project_exists
)
from config import ZENODO_MAX_PAGES, ZENODO_PAGE_SIZE, REPOSITORIES

REPO       = REPOSITORIES[1]
REPO_ID    = 1
REPO_URL   = REPO["url"]
REPO_NAME  = REPO["name"]
METHOD     = REPO["method"]


class ZenodoSearcher(BaseSearcher):

    name       = "Zenodo"
    SEARCH_URL = "https://zenodo.org/api/records"

    def search(self, conn: sqlite3.Connection, queries: list[str]):
        print(f"\n[{self.name}] Starting — {len(queries)} queries")
        print(f"  Repository ID : {REPO_ID}")
        print(f"  Max per query : {ZENODO_MAX_PAGES * ZENODO_PAGE_SIZE:,} records")
        total_saved = 0

        for query in queries:
            saved = self._run_query(conn, query)
            total_saved += saved
            print(f"  query='{query}' → {saved} new projects saved")

        print(f"[{self.name}] Done — {total_saved} total projects saved.\n")

    def _run_query(self, conn: sqlite3.Connection, query: str) -> int:
        saved = 0

        for page in range(1, ZENODO_MAX_PAGES + 1):
            data = self.get_json(self.SEARCH_URL, params={
                "q":    query,
                "page": page,
                "size": ZENODO_PAGE_SIZE,
            })

            if not data:
                break

            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                break

            for hit in hits:
                project_id = self._save_hit(conn, hit, query)
                if project_id:
                    saved += 1

            self.polite_sleep()

        return saved

    def _save_hit(self, conn: sqlite3.Connection,
                  hit: dict, query: str) -> int | None:

        try:
            meta      = hit.get("metadata", {})
            record_id = str(hit.get("id", ""))
            project_url = (
                hit.get("links", {}).get("html", "")
                or hit.get("links", {}).get("self", "")
                or f"https://zenodo.org/records/{record_id}"
            )
            if project_exists(conn, project_url):
                return None
            license_id  = (meta.get("license") or {}).get("id", "")
            license_url = (
                f"https://creativecommons.org/licenses/{license_id}"
                if license_id else ""
            )
            doi = ""
            for identifier in meta.get("related_identifiers", []):
                if identifier.get("scheme") == "doi":
                    doi = f"https://doi.org/{identifier.get('identifier','')}"
                    break
            if not doi and meta.get("doi"):
                doi = f"https://doi.org/{meta['doi']}"
            language = meta.get("language", "")
            upload_date = meta.get("publication_date", "")
            version = meta.get("version", "")
            project_id = insert_project(conn, {
                "query_string":               query,
                "repository_id":              REPO_ID,
                "repository_url":             REPO_URL,
                "project_url":                project_url,
                "version":                    version,
                "title":                      meta.get("title", ""),
                "description":                (meta.get("description") or "")[:500],
                "language":                   language,
                "doi":                        doi,
                "upload_date":                upload_date,
                "download_repository_folder": REPO_NAME,
                "download_project_folder":    record_id,
                "download_version_folder":    version or None,
                "download_method":            METHOD,
                "license":                    license_id,
                "license_url":                license_url,
            })

            if not project_id:
                return None
            raw_keywords = meta.get("keywords", []) or []
            insert_keywords(conn, project_id, raw_keywords)
            persons = []
            for creator in meta.get("creators", []):
                name = creator.get("name", "").strip()
                if name:
                    persons.append({"name": name, "role": "AUTHOR"})
            uploader = (meta.get("upload_type") or "")
            owner = hit.get("owners", [])
            if owner:
                persons.append({
                    "name": f"owner_id:{owner[0]}",
                    "role": "UPLOADER"
                })

            insert_persons(conn, project_id, persons)

            return project_id

        except Exception as e:
            self.log(f"[WARN] Could not save hit: {e}")
            return None