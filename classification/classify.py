import sqlite3
import json
import zipfile
from pathlib import Path

db_file = "../23240175-seeding.db"
archive_dir = Path("../acquisition/archive")

text_exts = {".txt", ".html", ".htm", ".md", ".csv"}
odt_exts = {".odt"}
pdf_exts = {".pdf"}
zip_exts = {".zip", ".qdpx"}

primary_exts = {
    "txt", "pdf", "docx", "doc", "rtf", "odt", "html", "htm",
    "mp3", "wav", "m4a", "mp4", "mov",
}

max_chars_per_file = 50000


def load_taxonomy():
    with open("isic_keywords_map.json", encoding="utf-8") as f:
        return json.load(f)


def classify_text(text, taxonomy):
    if not text:
        return "V-00"
    t = text.lower()
    scores = {}
    for code, info in taxonomy.items():
        s = sum(t.count(kw) for kw in info["keywords"] if kw)
        if s > 0:
            scores[code] = s
    if not scores:
        return "V-00"
    return max(scores, key=scores.get)


def read_txt(path):
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars_per_file]
    except:
        return ""


def read_odt(path):
    try:
        with zipfile.ZipFile(path) as z:
            with z.open("content.xml") as f:
                raw = f.read().decode("utf-8", errors="ignore")
                # strip xml tags
                import re
                text = re.sub(r"<[^>]+>", " ", raw)
                return text[:max_chars_per_file]
    except:
        return ""


def read_pdf(path):
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
            if len(text) > max_chars_per_file:
                break
        return text[:max_chars_per_file]
    except:
        return ""


def read_zip(path):
    text = ""
    try:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                ext = Path(name).suffix.lower()
                if ext in (".txt", ".html", ".htm"):
                    try:
                        with z.open(name) as f:
                            text += f.read().decode("utf-8", errors="ignore")
                    except:
                        pass
                if len(text) > max_chars_per_file:
                    break
    except:
        pass
    return text[:max_chars_per_file]


def get_text_from_file(path):
    ext = path.suffix.lower()
    if ext in text_exts:
        return read_txt(path)
    if ext in odt_exts:
        return read_odt(path)
    if ext in pdf_exts:
        return read_pdf(path)
    if ext in zip_exts:
        return read_zip(path)
    return ""


def locate_project_folder(folder_name):
    if not folder_name:
        return None
    for repo_dir in archive_dir.iterdir():
        if repo_dir.is_dir():
            maybe = repo_dir / folder_name
            if maybe.exists():
                return maybe
    return None

def main():
    if not archive_dir.exists():
        print(f"Folder not found: {archive_dir.resolve()}")
        return

    taxonomy = load_taxonomy()
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row

    pcols = [c[1] for c in conn.execute("PRAGMA table_info(projects)")]
    if "class" not in pcols:
        conn.execute("ALTER TABLE projects ADD COLUMN class TEXT")
    fcols = [c[1] for c in conn.execute("PRAGMA table_info(files)")]
    if "class" not in fcols:
        conn.execute("ALTER TABLE files ADD COLUMN class TEXT")
    conn.commit()

    #Tier 2
    projects = conn.execute("""
        SELECT id, title, description, download_project_folder, type
        FROM projects
        WHERE type IN ('QDA_PROJECT', 'QD_PROJECT')
    """).fetchall()

    print(f"Classifying {len(projects)} QDA+QD projects:")

    cur = conn.cursor()
    tier2_count = 0
    class_counts = {}

    for i, proj in enumerate(projects, 1):
        pid = proj["id"]

        # tier 1
        kw_rows = conn.execute(
            "SELECT keyword FROM keywords WHERE project_id=?", (pid,)
        ).fetchall()
        kw_text = " ".join(k[0] for k in kw_rows if k[0])
        meta_text = " ".join(filter(None, [proj["title"], proj["description"], kw_text]))

        # tier 2
        file_text = ""
        folder = locate_project_folder(proj["download_project_folder"])
        if folder:
            for f in folder.iterdir():
                if f.is_file() and f.name != "_metadata.json":
                    txt = get_text_from_file(f)
                    if txt:
                        file_text += " " + txt
                    if len(file_text) > max_chars_per_file * 2:
                        break
            if file_text.strip():
                tier2_count += 1

        combined = meta_text + " " + file_text
        pclass = classify_text(combined, taxonomy)
        cur.execute("UPDATE projects SET class=? WHERE id=?", (pclass, pid))
        class_counts[pclass] = class_counts.get(pclass, 0) + 1

        files = conn.execute(
            "SELECT id, file_name, file_type FROM files WHERE project_id=?", (pid,)
        ).fetchall()
        for fr in files:
            ft = (fr["file_type"] or "").lower().lstrip(".")
            if ft in primary_exts:
                fclass = classify_text(
                    (fr["file_name"] or "") + " " + combined, taxonomy
                )
                cur.execute("UPDATE files SET class=? WHERE id=?", (fclass, fr["id"]))

        if i % 5 == 0:
            conn.commit()
            print(f"  {i}/{len(projects)}  (tier 2 used for {tier2_count})")

    conn.commit()

    print(f"\n{'='*60}")
    print("Classification completed:")
    print(f"{'='*60}")
    print(f"Projects processed: {len(projects)}")
    print(f"Content read: {tier2_count} projects")
    print(f"\nTop classes:")
    for code in sorted(class_counts, key=class_counts.get, reverse=True)[:12]:
        title = taxonomy.get(code, {}).get("title", "Unknown")
        print(f"    {code:<6} {title[:38]:<38} {class_counts[code]:>4}")
    print(f"{'='*60}")

    conn.close()


if __name__ == "__main__":
    main()