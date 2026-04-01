import os
import time
import socket
import sqlite3
import requests
from abc import ABC, abstractmethod

from config import (
    HEADERS, REQUEST_TIMEOUT, REQUEST_RETRIES,
    POLITE_DELAY, OPEN_LICENSE_KEYWORDS,
    QDA_EXTENSIONS, PRIMARY_EXTENSIONS,
)

_orig_getaddrinfo = socket.getaddrinfo

def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = _getaddrinfo_ipv4


class BaseSearcher(ABC):

    name: str = "Unknown"
    def get_json(self, url: str, params: dict = None) -> dict | None:
        for attempt in range(REQUEST_RETRIES):
            try:
                resp = requests.get(
                    url, params=params,
                    headers=HEADERS,
                    timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                return resp.json()

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else 0
                if status == 429:
                    wait = 60
                    self.log(f"Rate limited (429) — waiting {wait}s…")
                elif status in (500, 502, 503, 504):
                    wait = 2 ** attempt
                    self.log(f"Server error ({status}) — retrying in {wait}s…")
                else:
                    self.log(f"HTTP {status} — skipping. Detail: {e}")
                    return None
                time.sleep(wait)

            except requests.exceptions.SSLError as e:
                self.log(f"SSL error — retrying in 5s…")
                self.log(f"  Detail: {e}")
                time.sleep(5)

            except requests.exceptions.ConnectionError as e:
                wait = 2 ** attempt
                self.log(f"Connection error — retrying in {wait}s…")
                self.log(f"  Detail: {e}")
                time.sleep(wait)

            except requests.exceptions.Timeout:
                wait = 2 ** attempt
                self.log(f"Timeout — retrying in {wait}s…")
                time.sleep(wait)

            except requests.RequestException as e:
                wait = 2 ** attempt
                self.log(f"Request error ({type(e).__name__}) — retrying in {wait}s…")
                self.log(f"  Detail: {e}")
                time.sleep(wait)

        self.log(f"Giving up after {REQUEST_RETRIES} attempts: {url}")
        return None

    def polite_sleep(self):
        time.sleep(POLITE_DELAY)

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

    @abstractmethod
    def search(self, conn: sqlite3.Connection, queries: list[str]):
        ...