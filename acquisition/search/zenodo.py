"""
search/zenodo.py — Searcher for Zenodo (https://zenodo.org)

Why Zenodo:
  - Fully open API, no key or login needed
  - Supports direct file-extension search (e.g. q=qdpx)
  - Returns full file lists in one API call
  - Largest collection of QDA files of any public repository
  - Rich, consistent metadata (license, authors, keywords, date)

API docs: https://developers.zenodo.org/#list36
"""

import json
import sqlite3

from search.base import BaseSearcher
from db import insert_project
from config import ZENODO_BASE_URL, ZENODO_MAX_PAGES, ZENODO_PAGE_SIZE


class ZenodoSearcher(BaseSearcher):

    name = "Zenodo"

    def search(self, conn: sqlite3.Connection, queries: list[str]):
        print(f"\n[{self.name}] Starting — {len(queries)} queries across {ZENODO_MAX_PAGES} pages each")
        total_saved = 0

        for query in queries:
            saved = self._run_query(conn, query)
            total_saved += saved
            print(f"  query='{query}' → {saved} new projects saved")

        print(f"[{self.name}] Done — {total_saved} total projects saved.\n")

    # ── Query loop ─────────────────────────────────────────────────────────────

    def _run_query(self, conn: sqlite3.Connection, query: str) -> int:
        saved = 0

        for page in range(1, ZENODO_MAX_PAGES + 1):
            data = self.get_json(ZENODO_BASE_URL, params={
                "q":            query,
                "access_right": "open",     # open-access only
                "type":         "dataset",  # datasets only (not papers)
                "page":         page,
                "size":         ZENODO_PAGE_SIZE,
            })

            if not data:
                break

            hits = data.get("hits", {}).get("hits", [])
            if not hits:
                break   # no more results for this query

            for hit in hits:
                record = self._parse(hit)
                if record and self.has_open_license(record["license"]):
                    if insert_project(conn, record):
                        saved += 1

            self.polite_sleep()

        return saved

    # ── Parser ─────────────────────────────────────────────────────────────────

    def _parse(self, hit: dict) -> dict | None:
        """Map one Zenodo API hit to a flat DB record dict."""
        try:
            meta       = hit.get("metadata", {})
            license_id = (meta.get("license") or {}).get("id", "")
            file_names = [f["key"] for f in hit.get("files", [])]
            qda_types  = self.detect_qda_types(file_names)

            return {
                "source":            self.name,
                "source_link":       hit.get("links", {}).get("html", ""),
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
                "download_url":      hit.get("links", {}).get("html", ""),
                "raw_metadata":      json.dumps(meta)[:2000],
            }
        except Exception as e:
            self.log(f"[WARN] Could not parse hit: {e}")
            return None