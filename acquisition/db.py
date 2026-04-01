import sqlite3

from config import DB_PATH


SCHEMA_SQL = """

CREATE TABLE IF NOT EXISTS projects (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    query_string                TEXT,
    repository_id               INTEGER NOT NULL,
    repository_url              TEXT    NOT NULL,
    project_url                 TEXT    UNIQUE NOT NULL,
    version                     TEXT,
    title                       TEXT    NOT NULL,
    description                 TEXT,
    language                    TEXT,
    doi                         TEXT,
    upload_date                 TEXT,
    download_date               TEXT,
    download_repository_folder  TEXT,
    download_project_folder     TEXT,
    download_version_folder     TEXT,
    download_method             TEXT    CHECK(download_method IN ('API-CALL','SCRAPING')),
    license                     TEXT,
    license_url                 TEXT
);

CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id),
    file_name   TEXT    NOT NULL,
    file_type   TEXT,
    status      TEXT    CHECK(status IN (
                    'SUCCEEDED',
                    'FAILED_SERVER_UNRESPONSIVE',
                    'FAILED_LOGIN_REQUIRED',
                    'FAILED_TOO_LARGE'
                ))
);

CREATE TABLE IF NOT EXISTS keywords (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id),
    keyword     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS person_role (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL REFERENCES projects(id),
    name        TEXT    NOT NULL,
    role        TEXT    CHECK(role IN (
                    'UPLOADER','AUTHOR','OWNER','OTHER','UNKNOWN'
                ))
);

"""

VALID_FILE_STATUSES = {
    "SUCCEEDED",
    "FAILED_SERVER_UNRESPONSIVE",
    "FAILED_LOGIN_REQUIRED",
    "FAILED_TOO_LARGE",
}

VALID_PERSON_ROLES = {"UPLOADER", "AUTHOR", "OWNER", "OTHER", "UNKNOWN"}


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    print(f"[DB] Initialised → '{db_path}'")
    return conn

def insert_project(conn: sqlite3.Connection, record: dict) -> int | None:
    required = ("repository_id", "repository_url", "project_url", "title")
    for key in required:
        if not record.get(key):
            print(f"  [DB WARN] Skipping record — missing required field '{key}'")
            return None

    try:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO projects (
                query_string,
                repository_id,
                repository_url,
                project_url,
                version,
                title,
                description,
                language,
                doi,
                upload_date,
                download_repository_folder,
                download_project_folder,
                download_version_folder,
                download_method,
                license,
                license_url
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            record.get("query_string"),
            record["repository_id"],
            record["repository_url"],
            record["project_url"],
            record.get("version"),
            record["title"],
            record.get("description"),
            record.get("language"),
            record.get("doi"),
            record.get("upload_date"),
            record.get("download_repository_folder"),
            record.get("download_project_folder"),
            record.get("download_version_folder"),
            record.get("download_method"),
            record.get("license"),
            record.get("license_url"),
        ))
        conn.commit()
        return cursor.lastrowid if cursor.rowcount == 1 else None

    except sqlite3.Error as e:
        print(f"  [DB ERROR] insert_project: {e}")
        return None


def update_project(conn: sqlite3.Connection, project_id: int, fields: dict):
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    try:
        conn.execute(
            f"UPDATE projects SET {set_clause} WHERE id = ?",
            list(fields.values()) + [project_id],
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"  [DB ERROR] update_project id={project_id}: {e}")


def project_exists(conn: sqlite3.Connection, project_url: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM projects WHERE project_url = ?", (project_url,)
    ).fetchone()
    return row is not None


def get_all_projects(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM projects ORDER BY repository_id, id"
    ).fetchall()


def get_projects_by_repo(conn: sqlite3.Connection,
                         repository_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM projects WHERE repository_id = ? ORDER BY id",
        (repository_id,)
    ).fetchall()

def insert_file(conn: sqlite3.Connection,
                project_id: int,
                file_name: str,
                file_type: str,
                status: str) -> int | None:

    if status not in VALID_FILE_STATUSES:
        print(f"  [DB WARN] Invalid status '{status}' for file '{file_name}', defaulting to FAILED_SERVER_UNRESPONSIVE")
        status = "FAILED_SERVER_UNRESPONSIVE"

    try:
        cursor = conn.execute("""
            INSERT INTO files (project_id, file_name, file_type, status)
            VALUES (?, ?, ?, ?)
        """, (project_id, file_name, file_type, status))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"  [DB ERROR] insert_file: {e}")
        return None


def get_files_for_project(conn: sqlite3.Connection,
                           project_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM files WHERE project_id = ? ORDER BY id",
        (project_id,)
    ).fetchall()


def insert_keywords(conn: sqlite3.Connection,
                    project_id: int,
                    keywords: list[str]):
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        try:
            conn.execute(
                "INSERT INTO keywords (project_id, keyword) VALUES (?, ?)",
                (project_id, kw)
            )
        except sqlite3.Error as e:
            print(f"  [DB ERROR] insert_keyword '{kw}': {e}")
    conn.commit()


def get_keywords_for_project(conn: sqlite3.Connection,
                              project_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT keyword FROM keywords WHERE project_id = ? ORDER BY id",
        (project_id,)
    ).fetchall()
    return [r["keyword"] for r in rows]

def insert_person(conn: sqlite3.Connection,
                  project_id: int,
                  name: str,
                  role: str = "UNKNOWN"):
    if role not in VALID_PERSON_ROLES:
        role = "UNKNOWN"

    name = (name or "").strip()
    if not name:
        return

    try:
        conn.execute(
            "INSERT INTO person_role (project_id, name, role) VALUES (?, ?, ?)",
            (project_id, name, role)
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"  [DB ERROR] insert_person '{name}': {e}")


def insert_persons(conn: sqlite3.Connection,
                   project_id: int,
                   persons: list[dict]):
    for p in persons:
        insert_person(conn, project_id, p.get("name", ""), p.get("role", "UNKNOWN"))


def get_persons_for_project(conn: sqlite3.Connection,
                             project_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM person_role WHERE project_id = ? ORDER BY id",
        (project_id,)
    ).fetchall()

def summary(conn: sqlite3.Connection) -> dict:
    total_projects = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    total_files    = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]

    file_counts = {
        row[0]: row[1]
        for row in conn.execute("""
            SELECT status, COUNT(*)
            FROM files
            GROUP BY status
        """)
    }

    by_repo = {
        row[1]: row[2]
        for row in conn.execute("""
            SELECT repository_id, repository_url, COUNT(*)
            FROM projects
            GROUP BY repository_id
            ORDER BY repository_id
        """)
    }

    return {
        "total_projects": total_projects,
        "total_files":    total_files,
        "files": {
            "succeeded":          file_counts.get("SUCCEEDED", 0),
            "failed_login":       file_counts.get("FAILED_LOGIN_REQUIRED", 0),
            "failed_too_large":   file_counts.get("FAILED_TOO_LARGE", 0),
            "failed_server":      file_counts.get("FAILED_SERVER_UNRESPONSIVE", 0),
        },
        "by_repository": by_repo,
    }