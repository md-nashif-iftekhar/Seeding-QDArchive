"""
search/base.py — Shared base class for all repository searchers.

Provides:
    get_json()            — HTTP GET with retry + back-off
    has_open_license()    — license string check
    detect_qda_types()    — find QDA extensions in a file list
    detect_primary_data() — check for primary data files
    search()              — abstract method every subclass must implement
"""

import os
import time
import sqlite3
import requests
from abc import ABC, abstractmethod

from config import (
    HEADERS, REQUEST_TIMEOUT, REQUEST_RETRIES,
    POLITE_DELAY, OPEN_LICENSE_KEYWORDS,
    QDA_EXTENSIONS, PRIMARY_EXTENSIONS,
)


class BaseSearcher(ABC):

    name: str = "Unknown"

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def get_json(self, url: str, params: dict = None) -> dict | None:
        for attempt in range(REQUEST_RETRIES):
            try:
                resp = requests.get(
                    url, params=params,
                    headers=HEADERS, timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else "?"
                wait   = (2 ** attempt) * (10 if status == 429 else 1)
                self.log(f"HTTP {status} — waiting {wait}s…")
                time.sleep(wait)
            except requests.RequestException as e:
                wait = 2 ** attempt
                self.log(f"{e} — retrying in {wait}s…")
                time.sleep(wait)
        self.log(f"Giving up after {REQUEST_RETRIES} attempts: {url}")
        return None

    def polite_sleep(self):
        time.sleep(POLITE_DELAY)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def has_open_license(self, license_str: str) -> bool:
        if not license_str:
            return False
        lower = license_str.lower()
        return any(kw in lower for kw in OPEN_LICENSE_KEYWORDS)

    def detect_qda_types(self, filenames: list[str]) -> list[str]:
        found = set()
        for fname in filenames:
            ext = os.path.splitext(fname.lower())[1]
            if ext in QDA_EXTENSIONS:
                found.add(ext)
        return sorted(found)

    def detect_primary_data(self, filenames: list[str]) -> bool:
        for fname in filenames:
            ext = os.path.splitext(fname.lower())[1]
            if ext in PRIMARY_EXTENSIONS:
                return True
        return False

    def log(self, msg: str):
        print(f"  [{self.name}] {msg}")

    # ── Interface ─────────────────────────────────────────────────────────────

    @abstractmethod
    def search(self, conn: sqlite3.Connection, queries: list[str]):
        ...