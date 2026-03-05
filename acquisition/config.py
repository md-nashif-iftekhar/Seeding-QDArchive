"""
config.py — Central configuration for the QDArchive acquisition pipeline.
Edit this file to tune behaviour without touching any other file.
"""

# ── Paths ──────────────────────────────────────────────────────────────────────

DB_PATH      = "qdarchive.db"
ARCHIVE_DIR  = "archive"
CSV_PATH     = "qdarchive_export.csv"
REPORT_PATH  = "report.txt"

# ── HTTP ───────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "QDArchive-Seeder/1.0 (research project; FAU Erlangen)"
}

REQUEST_TIMEOUT  = 30               # seconds per request
REQUEST_RETRIES  = 3                # retries on failure
POLITE_DELAY     = 1.0              # seconds between API calls
FILE_DELAY       = 0.5              # seconds between file downloads
MAX_FILE_SIZE    = 500 * 1024 * 1024  # skip files > 500 MB (unless QDA)

# ── Zenodo settings ────────────────────────────────────────────────────────────

ZENODO_BASE_URL  = "https://zenodo.org/api/records"
ZENODO_MAX_PAGES = 10
ZENODO_PAGE_SIZE = 25

# ── QDA File Extensions ────────────────────────────────────────────────────────
# Source: QDA_File_Extensions_Formats.xlsx

QDA_EXTENSIONS = {
    # REFI standard / QDAcity
    ".qdpx", ".qdc",
    # MaxQDA
    ".mqda", ".mqbac", ".mqtc", ".mqex", ".mqmtr",
    ".mx24", ".mx24bac", ".mc24", ".mex24",
    ".mx22", ".mx20", ".mx18", ".mx12", ".mx11",
    ".mx5",  ".mx4",  ".mx3",  ".mx2",  ".m2k",
    ".loa",  ".sea",  ".mtr",  ".mod",  ".mex22",
    # NVivo
    ".nvp", ".nvpx",
    # ATLAS.ti
    ".atlasproj", ".hpr7",
    # f4analyse
    ".f4p",
    # QDA Miner
    ".ppj", ".pprj", ".qlt",
    # Quirkos
    ".qpd",
}

# ── Primary Data Extensions ────────────────────────────────────────────────────

PRIMARY_EXTENSIONS = {
    ".txt", ".pdf", ".rtf", ".docx", ".doc",
    ".odt", ".md",  ".tex",
}

# ── Open License Keywords ──────────────────────────────────────────────────────

OPEN_LICENSE_KEYWORDS = [
    "cc-by", "cc by", "creative commons",
    "cc0", "cc-0", "public domain",
    "open access",
    "cc-by-sa", "cc-by-nc", "cc-by-nd",
    "cc-by-nc-sa", "cc-by-nc-nd",
    "mit", "apache", "gpl",
]

# ── Search Queries ─────────────────────────────────────────────────────────────
# Targeting QDA file types directly (most precise)
QUERIES_QDA = [
    "qdpx",
    "qdc",
    "nvp",
    "atlasproj",
    "maxqda",
    "nvivo",
    "atlas.ti",
    "f4analyse",
    "quirkos",
    "QDA miner",
]

# Targeting qualitative research broadly
QUERIES_QUALITATIVE = [
    "qualitative research",
    "qualitative data",
    "interview transcript",
    "thematic analysis",
    "grounded theory",
    "content analysis",
    "focus group",
    "ethnographic research",
    "narrative analysis",
    "discourse analysis",
]

ALL_QUERIES = QUERIES_QDA + QUERIES_QUALITATIVE