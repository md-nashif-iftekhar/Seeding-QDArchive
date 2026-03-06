import json
import sqlite3

from search.base import BaseSearcher
from db import insert_project
from config import ZENODO_MAX_PAGES, ZENODO_PAGE_SIZE


class ZenodoSearcher(BaseSearcher):

    name       = "Zenodo"
    SEARCH_URL = "https://zenodo.org/api/records"

    def search(self, conn: sqlite3.Connection, queries: list[str]):
        print(f"\n[{self.name}] Starting — {len(queries)} queries")
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
                "sort": "bestmatch",
            })

            if not data:
                break

            hits = data.get("hits", {}).get("hits", [])

            if not hits:
                break

            for hit in hits:
                record = self._parse(hit)
                if record:
                    if insert_project(conn, record):
                        saved += 1

            self.polite_sleep()

        return saved

    def _parse(self, hit: dict) -> dict | None:
        """Map one Zenodo API hit to a flat DB record dict."""
        try:
            meta      = hit.get("metadata", {})
            record_id = hit.get("id", "")
            source_link = (
                hit.get("links", {}).get("html", "")
                or hit.get("links", {}).get("self", "")
                or f"https://zenodo.org/records/{record_id}"
            )

            license_id = (meta.get("license") or {}).get("id", "")
            file_names = [f["key"] for f in hit.get("files", [])]
            qda_types  = self.detect_qda_types(file_names)

            return {
                "source":            self.name,
                "source_link":       source_link,
                "title":             meta.get("title", ""),
                "description":       (meta.get("description") or "")[:500],
                "license":           license_id,
                "license_url":       f"https://creativecommons.org/licenses/{license_id}"
                                     if license_id else "",
                "authors":           json.dumps([
                    c.get("name", "") for c in meta.get("creators", [])
                ]),
                "keywords":          json.dumps(meta.get("keywords", [])),
                "publication_date":  meta.get("publication_date", ""),
                "has_qda_files":     1 if qda_types else 0,
                "qda_file_types":    json.dumps(qda_types),
                "has_primary_data":  1 if self.detect_primary_data(file_names) else 0,
                "file_count":        len(file_names),
                "download_url":      source_link,
                "raw_metadata":      json.dumps(meta)[:2000],
            }
        except Exception as e:
            self.log(f"[WARN] Could not parse hit: {e}")
            return None