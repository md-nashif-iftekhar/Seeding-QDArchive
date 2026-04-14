"""
search/sikt.py — Searcher for Sikt (Norwegian data archive)
https://sikt.no/en/find-data

Repository ID : 20
Method        : GraphQL API (api.nsd.no/graphql)

Technical findings:
  - SIKT set removed from CESSDA OAI-PMH catalogue (April 2026)
  - Surveybanken uses a GraphQL API at https://api.nsd.no/graphql
  - Query: elasticSearch.searchForStudiesQuery with kindOfData: QUALITATIVE
  - Pagination via cursor (first/after)
  - Repo: FORSKNINGSDATA
  - Full metadata available: title, abstract, subjects, topics, restrictions
  - License/DOI not in ElasticStudyNode — fetched separately via studyMetadata
"""

import re
import time
import sqlite3
from datetime import datetime

import requests

from config import (
    REPOSITORIES, HEADERS, FILE_DELAY,
    SIKT_OAI_URL, SIKT_MAX_RECORDS,
)
from db import init_db, insert_project, insert_keywords, insert_person
from search.base import BaseSearcher

REPO_ID       = 20
REPO          = REPOSITORIES[REPO_ID]
SIKT_GRAPHQL  = "https://api.nsd.no/graphql"
SIKT_STUDY_URL = "https://surveybanken.sikt.no/en/study/{id}/{version}"

GQL_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent":   "QDArchive-Seeder/1.0 (FAU Erlangen)",
    "Referer":      "https://surveybanken.sikt.no/",
    "Origin":       "https://surveybanken.sikt.no",
}

SEARCH_QUERY = """
query SearchStudies($query: [String!]!, $first: Int, $after: String) {
  elasticSearch {
    searchForStudiesQuery(
      input: {
        query: $query
        dataAccess: [OPEN]
        first: $first
        after: $after
      }
      repo: FORSKNINGSDATA
    ) {
      pageInfo { hasNextPage endCursor }
      edges {
        cursor
        node {
          id
          version
          studyNumber
          title { en no }
          abstract { en no }
          kindOfData
          topic
          subjects { en no }
          restrictions { en no }
          startDate
          endDate
          caseQuantity
          citation { publisher { en no } }
          parentSeries { id title { en no } }
        }
      }
    }
  }
}
"""

# Keywords that indicate qualitative data
QUALITATIVE_KEYWORDS = [
    "qualitative", "interview", "focus group", "transcript",
    "fieldnote", "ethnograph", "narrative", "discourse",
    "thematic", "grounded theory", "case study", "oral history",
    "text", "audio", "video", "observation",
]


class SiktSearcher(BaseSearcher):

    name   = REPO["name"]
    OAI_URL = SIKT_GRAPHQL

    def search(self, conn: sqlite3.Connection, queries: list[str]):
        print(f"\n[Sikt] Starting GraphQL harvest…")
        print(f"  Repository ID : {REPO_ID}")
        print(f"  API           : {SIKT_GRAPHQL}")
        print(f"  Filter        : dataAccess=OPEN, qualitative keywords")

        saved      = 0
        seen_ids   = set()
        total_seen = 0

        for query_str in queries:
            print(f"\n  Query: {query_str!r}")
            cursor = None
            page   = 0

            while total_seen < SIKT_MAX_RECORDS:
                data = self._fetch_page(query_str, cursor)
                if data is None:
                    break

                edges     = data.get("edges", [])
                page_info = data.get("pageInfo", {})

                for edge in edges:
                    node = edge.get("node", {})
                    uid  = node.get("id", "")

                    if uid in seen_ids:
                        continue
                    seen_ids.add(uid)
                    total_seen += 1

                    # Filter: keep Text/Audio kindOfData
                    # OR title/abstract contains qualitative keywords
                    kind = (node.get("kindOfData") or "").lower()
                    title_obj    = node.get("title") or {}
                    abstract_obj = node.get("abstract") or {}
                    combined = " ".join([
                        title_obj.get("en") or "",
                        title_obj.get("no") or "",
                        abstract_obj.get("en") or "",
                        abstract_obj.get("no") or "",
                        kind,
                    ]).lower()

                    is_qualitative = (
                        kind in ("text", "audio", "qualitative", "other") or
                        any(kw in combined for kw in QUALITATIVE_KEYWORDS)
                    )
                    if not is_qualitative:
                        continue

                    parsed = self._parse_node(node)
                    if parsed is None:
                        continue

                    pid = self._save_record(conn, parsed)
                    if pid:
                        saved += 1

                    if total_seen % 50 == 0:
                        print(f"    Seen: {total_seen}, saved: {saved}")

                if page_info.get("hasNextPage") and page_info.get("endCursor"):
                    cursor = page_info["endCursor"]
                    page  += 1
                    time.sleep(FILE_DELAY)
                else:
                    break

            print(f"  Done with query {query_str!r} — saved so far: {saved}")

        print(f"\n[Sikt] Done — {saved} qualitative projects saved.\n")

    # ── GraphQL fetch ──────────────────────────────────────────────────────────

    def _fetch_page(self, query_str: str, after: str = None) -> dict | None:
        variables = {
            "query": [query_str],
            "first": 50,
        }
        if after:
            variables["after"] = after

        try:
            resp = requests.post(
                SIKT_GRAPHQL,
                json={"query": SEARCH_QUERY, "variables": variables},
                headers=GQL_HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()

            if "errors" in result:
                for err in result["errors"]:
                    self.log(f"[ERROR] GraphQL: {err.get('message')}")
                return None

            return (result.get("data", {})
                         .get("elasticSearch", {})
                         .get("searchForStudiesQuery"))

        except Exception as e:
            self.log(f"[ERROR] fetch failed: {e}")
            return None

    # ── Parse node ─────────────────────────────────────────────────────────────

    def _parse_node(self, node: dict) -> dict | None:
        uid          = node.get("id", "")
        version      = node.get("version", 1)
        study_number = node.get("studyNumber", "")

        title_obj = node.get("title") or {}
        title     = title_obj.get("en") or title_obj.get("no") or ""
        if not title:
            return None

        abstract_obj = node.get("abstract") or {}
        description  = abstract_obj.get("en") or abstract_obj.get("no") or ""

        restrictions_obj = node.get("restrictions") or {}
        restrictions     = restrictions_obj.get("en") or restrictions_obj.get("no") or ""

        # Publisher / license from citation
        citation_obj  = node.get("citation") or {}
        publisher_obj = citation_obj.get("publisher") or {}
        publisher     = publisher_obj.get("en") or publisher_obj.get("no") or "Sikt"

        # Dates
        start_date = (node.get("startDate") or "")[:10]
        end_date   = (node.get("endDate") or "")[:10]
        upload_date = end_date or start_date or ""

        # Keywords from subjects
        subjects = node.get("subjects") or []
        keywords = []
        for s in subjects:
            kw = s.get("en") or s.get("no") or ""
            if kw:
                keywords.append(kw)

        # Also add topic codes as keywords
        for t in node.get("topic") or []:
            keywords.append(t)

        # Study URL
        project_url = SIKT_STUDY_URL.format(id=uid, version=version)

        # Determine license from restrictions text
        rest_lower = restrictions.lower()
        if not restrictions:
            license_str = "CC BY 4.0"
        elif any(kw in rest_lower for kw in
                 ["processing agreement", "data agreement",
                  "person identif", "sensitive"]):
            license_str = "Restricted"
        elif any(kw in rest_lower for kw in ["cc", "open", "freely"]):
            license_str = "CC BY 4.0"
        else:
            license_str = "Unknown"

        return {
            "query_string":               "",
            "repository_id":              REPO_ID,
            "repository_url":             REPO["url"],
            "project_url":                project_url,
            "version":                    str(version),
            "title":                      title,
            "description":                description,
            "language":                   "no/en",
            "doi":                        "",
            "upload_date":                upload_date,
            "download_repository_folder": REPO["name"],
            "download_project_folder":    study_number or uid,
            "download_version_folder":    str(version),
            "download_method":            "SCRAPING",
            "license":                    license_str,
            "license_url":                "",
            "_keywords":                  keywords,
            "_publisher":                 publisher,
        }

    # ── Save to DB ─────────────────────────────────────────────────────────────

    def _save_record(self, conn: sqlite3.Connection, record: dict) -> int | None:
        keywords  = record.pop("_keywords", [])
        publisher = record.pop("_publisher", "")

        pid = insert_project(conn, record)
        if pid is None:
            return None

        for kw in keywords:
            insert_keywords(conn, pid, [kw])

        if publisher:
            insert_person(conn, pid, name=publisher, role="OWNER")

        return pid