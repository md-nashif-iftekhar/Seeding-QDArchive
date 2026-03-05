"""
search/__init__.py — Exports ALL_SEARCHERS.

Currently: Zenodo only (best source for QDA files).
To add another repository later:
  1. Create search/myrepo.py inheriting BaseSearcher
  2. Import and add to ALL_SEARCHERS below
"""

from search.zenodo import ZenodoSearcher

ALL_SEARCHERS = [
    ZenodoSearcher(),
]