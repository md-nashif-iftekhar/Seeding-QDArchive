import argparse
import traceback

from config import DB_PATH, ALL_QUERIES
from db import init_db, summary
from search import ALL_SEARCHERS


REPO_NAME_MAP = {
    "zenodo": "Zenodo",
    "fsd":    "FSD",
    "sikt":   "Sikt",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="QDArchive — search repositories and collect metadata"
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=REPO_NAME_MAP.keys(),
        help="Only search specified repositories (default: all). Example: --only fsd sikt"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.only:
        selected = {REPO_NAME_MAP[r] for r in args.only}
        searchers = [s for s in ALL_SEARCHERS if s.name in selected]
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
            traceback.print_exc()

    stats = summary(conn)
    conn.close()

    print("\n" + "=" * 60)
    print("SEARCH COMPLETE")
    print("=" * 60)
    print(f"  Total projects : {stats['total_projects']:,}")
    print()
    print("  By repository:")
    for repo_url, count in stats["by_repository"].items():
        print(f"    {repo_url:<45} {count:>6} projects")
    print()
    print(f"  Database       : {DB_PATH}")
    print("=" * 60)
    print("\nNext step:  python download.py")


if __name__ == "__main__":
    main()