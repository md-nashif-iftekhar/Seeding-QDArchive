"""
search.py — Step 1: Query all repositories and collect metadata into the database.

Run:
    python search.py                    # search all repositories
    python search.py --only zenodo      # Zenodo only
    python search.py --only fsd         # FSD only
    python search.py --only sikt        # Sikt only
    python search.py --only fsd sikt    # FSD and Sikt only

Output:
    qdarchive.db   — SQLite database with all collected project metadata
"""

import argparse

from config import DB_PATH, ALL_QUERIES
from db import init_db, summary
from search import ALL_SEARCHERS


def parse_args():
    parser = argparse.ArgumentParser(
        description="QDArchive — search repositories and collect metadata"
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=["zenodo", "fsd", "sikt"],
        metavar="REPO",
        help="Only search specified repositories. "
             "Choices: zenodo, fsd, sikt. "
             "Example: --only fsd sikt"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Filter searchers based on --only argument
    name_map = {
        "zenodo": "zenodo",
        "fsd":    "finnish-social-science-data-archive",
        "sikt":   "sikt",
    }

    if args.only:
        selected_names = [name_map[r] for r in args.only]
        searchers = [s for s in ALL_SEARCHERS if s.name in selected_names]
    else:
        searchers = ALL_SEARCHERS

    print("=" * 60)
    print("QDArchive — Part 1: Data Acquisition")
    print("search.py  — Querying repositories")
    print("=" * 60)
    print(f"  Repositories : {', '.join(s.name for s in searchers)}")
    print(f"  Queries      : {len(ALL_QUERIES)}")
    print(f"  Database     : {DB_PATH}")
    print("=" * 60)

    conn = init_db(DB_PATH)

    for searcher in searchers:
        try:
            searcher.search(conn, queries=ALL_QUERIES)
        except KeyboardInterrupt:
            print(f"\n[Interrupted] Stopped at {searcher.name}. Progress saved.")
            break
        except Exception as e:
            print(f"[ERROR] {searcher.name}: {e}")
            import traceback
            traceback.print_exc()

    stats = summary(conn)
    conn.close()

    print("\n" + "=" * 60)
    print("SEARCH COMPLETE")
    print("=" * 60)
    print(f"  Total projects : {stats['total_projects']:,}")
    print(f"")
    print(f"  By repository:")
    for repo_url, count in stats["by_repository"].items():
        print(f"    {repo_url:<45} {count:>6} projects")
    print(f"")
    print(f"  Database       : {DB_PATH}")
    print("=" * 60)
    print("\nNext step:  python download.py")


if __name__ == "__main__":
    main()