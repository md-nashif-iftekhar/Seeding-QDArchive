import json
import sqlite3
from datetime import datetime

from config import DB_PATH

CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS projects (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        source           TEXT,
        source_link      TEXT UNIQUE,
        title            TEXT,
        description      TEXT,
        license          TEXT,
        license_url      TEXT,
        authors          TEXT,
        keywords         TEXT,
        publication_date TEXT,
        has_qda_files    INTEGER DEFAULT 0,
        qda_file_types   TEXT    DEFAULT '[]',
        has_primary_data INTEGER DEFAULT 0,
        file_count       INTEGER,
        download_url     TEXT,
        raw_metadata     TEXT,
        collected_at     TEXT
    )
"""

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()
    print(f"[DB] Initialised → '{db_path}'")
    return conn

def insert_project(conn: sqlite3.Connection, record: dict) -> bool:
    record = {**record}
    record.setdefault("collected_at", datetime.utcnow().isoformat())
    record.setdefault("qda_file_types", "[]")

    for key, val in record.items():
        if isinstance(val, (list, dict)):
            record[key] = json.dumps(val)

    cols         = ", ".join(record.keys())
    placeholders = ", ".join("?" * len(record))

    try:
        cursor = conn.execute(
            f"INSERT OR IGNORE INTO projects ({cols}) VALUES ({placeholders})",
            list(record.values()),
        )
        conn.commit()
        return cursor.rowcount == 1
    except sqlite3.Error as e:
        print(f"  [DB ERROR] {e}")
        return False


def update_project(conn: sqlite3.Connection, project_id: int, fields: dict):
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields.keys())
    try:
        conn.execute(
            f"UPDATE projects SET {set_clause} WHERE id = ?",
            list(fields.values()) + [project_id],
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"  [DB ERROR] update id={project_id}: {e}")

def get_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM projects ORDER BY has_qda_files DESC, id ASC"
    ).fetchall()


def get_by_source(conn: sqlite3.Connection, source: str) -> list[sqlite3.Row]:
    """Fetch all rows for a specific source (e.g. 'Zenodo', 'FSD', 'Sikt')."""
    return conn.execute(
        "SELECT * FROM projects WHERE source = ? ORDER BY id ASC",
        (source,)
    ).fetchall()

def summary(conn: sqlite3.Connection) -> dict:
    total        = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    with_qda     = conn.execute("SELECT COUNT(*) FROM projects WHERE has_qda_files=1").fetchone()[0]
    with_primary = conn.execute("SELECT COUNT(*) FROM projects WHERE has_primary_data=1").fetchone()[0]

    by_source = {}
    for row in conn.execute(
        "SELECT source, COUNT(*) FROM projects GROUP BY source ORDER BY 2 DESC"
    ):
        by_source[row[0]] = row[1]

    return {
        "total":        total,
        "with_qda":     with_qda,
        "with_primary": with_primary,
        "by_source":    by_source,
    }