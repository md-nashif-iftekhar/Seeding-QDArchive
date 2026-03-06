DB_PATH      = "qdarchive.db"
ARCHIVE_DIR  = "archive"
CSV_PATH     = "qdarchive_export.csv"
REPORT_PATH  = "report.txt"
HEADERS = {
    "User-Agent": "QDArchive-Seeder/1.0 (research project; FAU Erlangen)"
}

REQUEST_TIMEOUT  = 30               # seconds per request
REQUEST_RETRIES  = 3                # retries on failure
POLITE_DELAY     = 1.0              # seconds between API calls
FILE_DELAY       = 0.5              # seconds between file downloads
MAX_FILE_SIZE    = 500 * 1024 * 1024  # skip files > 500 MB (unless QDA)

ZENODO_BASE_URL  = "https://zenodo.org/api/records"
ZENODO_MAX_PAGES = 20
ZENODO_PAGE_SIZE = 25

QDA_EXTENSIONS = {
    ".qdpx", ".qdc",
    ".mqda", ".mqbac", ".mqtc", ".mqex", ".mqmtr",
    ".mx24", ".mx24bac", ".mc24", ".mex24",
    ".mx22", ".mx20", ".mx18", ".mx12", ".mx11",
    ".mx5",  ".mx4",  ".mx3",  ".mx2",  ".m2k",
    ".loa",  ".sea",  ".mtr",  ".mod",  ".mex22",
    ".nvp", ".nvpx",
    ".atlasproj", ".hpr7",
    ".f4p",
    ".ppj", ".pprj", ".qlt",
    ".qpd",
}

PRIMARY_EXTENSIONS = {
    ".txt", ".pdf", ".rtf", ".docx", ".doc",
    ".odt", ".md",  ".tex",
}

OPEN_LICENSE_KEYWORDS = [
    "cc-by",
    "cc-by-sa",
    "cc-by-nc",
    "cc-by-nd",
    "cc0",
    "cc-zero",
    "public domain",
    "other-open",
    "other-at",
    "mit",
    "apache",
    "gpl",
]

QUERIES_QDA = [
    "qdpx",
    "refi-qda",
    "qdc qualitative",
    "maxqda",
    "nvivo",
    "atlas.ti",
    "atlasti",
    "f4analyse",
    "quirkos",
    "qdaminer",
    "dedoose",
]

QUERIES_QUALITATIVE = [
    "interview transcript qualitative",
    "thematic analysis data",
    "grounded theory interview",
    "qualitative content analysis",
    "focus group transcript",
    "ethnographic fieldnotes",
    "narrative inquiry data",
    "discourse analysis transcript",
]

ALL_QUERIES = QUERIES_QDA + QUERIES_QUALITATIVE