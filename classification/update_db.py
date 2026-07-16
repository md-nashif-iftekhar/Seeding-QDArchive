import sqlite3
import json

db_path = "../23240175-seeding.db"

qda_exts = {
    "qdpx", "qdp", "qdc", "nvp", "nvpx", "qde",
    "atlproj", "hpr7", "hpr", "mx20", "mx21", "mx22", "mx23", "mx24",
    "qda", "rqda", "qsproj", "dedoose", "f4w",
}

primary_exts = {
    "txt", "pdf", "docx", "doc", "rtf", "odt", "html", "htm", "md", "tex", "epub",
    "mp3", "wav", "m4a", "mp4", "mov", "avi", "wma", "aac",
    "srt", "vtt", "trs", "eaf", "cha",
}

other_exts = {
    "csv", "tab", "tsv", "xlsx", "xls", "ods", "json", "xml", "sav", "por",
    "dta", "dat", "zsav", "sps", "do", "r", "rdata", "dbf", "dic", "frq",
    "jpg", "jpeg", "png", "gif", "tif", "tiff", "zip", "cmdi", "lab",
}


def clean_ext(raw):
    return (raw or "").lower().strip().lstrip(".")


def get_project_type(extensions):
    normalised = {clean_ext(e) for e in extensions if e}
    if normalised & qda_exts:
        return "QDA_PROJECT"
    if normalised & primary_exts:
        return "QD_PROJECT"
    if normalised & other_exts:
        return "OTHER_PROJECT"
    return "NOT_A_PROJECT"


def guess_class(text_blob, taxonomy):
    if not text_blob:
        return "V-00"
    blob_lower = text_blob.lower()
    scores = {}
    for code, info in taxonomy.items():
        score = sum(blob_lower.count(kw) for kw in info["keywords"] if kw)
        if score > 0:
            scores[code] = score
    if not scores:
        return "V-00"
    return max(scores, key=scores.get)


def main():
    with open("isic_keywords_map.json", encoding="utf-8") as f:
        taxonomy = json.load(f)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    existing_cols = [c[1] for c in conn.execute("PRAGMA table_info(projects)").fetchall()]
    if "type" not in existing_cols:
        conn.execute("ALTER TABLE projects ADD COLUMN type TEXT")
    if "class" not in existing_cols:
        conn.execute("ALTER TABLE projects ADD COLUMN class TEXT")

    file_cols = [c[1] for c in conn.execute("PRAGMA table_info(files)").fetchall()]
    if "class" not in file_cols:
        conn.execute("ALTER TABLE files ADD COLUMN class TEXT")
    conn.commit()

    projects = conn.execute("SELECT id, title, description FROM projects").fetchall()
    print(f"Labelling {len(projects)} projects…")

    cur = conn.cursor()
    type_counts = {}

    for proj in projects:
        pid = proj["id"]

        ext_rows = conn.execute(
            "SELECT file_type FROM files WHERE project_id=?", (pid,)
        ).fetchall()
        exts = [r[0] for r in ext_rows]
        ptype = get_project_type(exts)
        type_counts[ptype] = type_counts.get(ptype, 0) + 1

        pclass = None
        if ptype in ("QDA_PROJECT", "QD_PROJECT"):
            kw_rows = conn.execute(
                "SELECT keyword FROM keywords WHERE project_id=?", (pid,)
            ).fetchall()
            kw_text = " ".join(k[0] for k in kw_rows if k[0])
            full_text = " ".join(filter(None, [proj["title"], proj["description"], kw_text]))
            pclass = guess_class(full_text, taxonomy)

        cur.execute("UPDATE projects SET type=?, class=? WHERE id=?",
                    (ptype, pclass, pid))

    conn.commit()

    print("\nProject type:")
    for t, n in type_counts.items():
        print(f"  {t:<16} {n:>5}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()