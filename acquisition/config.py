DB_PATH      = "qdarchive.db"
ARCHIVE_DIR  = "archive"
CSV_PATH     = "qdarchive_export.csv"
REPORT_PATH  = "report.txt"

HEADERS = {
    "User-Agent": "QDArchive-Seeder/1.0 (research project; FAU Erlangen)"
}

REQUEST_TIMEOUT  = 30
REQUEST_RETRIES  = 3
POLITE_DELAY     = 1.0
FILE_DELAY       = 0.5
MAX_FILE_SIZE    = 500 * 1024 * 1024

REPOSITORIES = {
    1:  {
        "name":   "zenodo",
        "url":    "https://zenodo.org",
        "method": "API-CALL",
    },
    11: {
        "name":   "finnish-social-science-data-archive",
        "url":    "https://www.fsd.tuni.fi/en",
        "method": "API-CALL",
    },
    20: {
        "name":   "sikt",
        "url":    "https://sikt.no/en/find-data",
        "method": "API-CALL",
    },
}

ZENODO_MAX_PAGES = 400
ZENODO_PAGE_SIZE = 25

FSD_OAI_URL     = "https://services.fsd.tuni.fi/v0/oai"
FSD_MAX_RECORDS = 2000

SIKT_OAI_URL     = "https://datacatalogue.cessda.eu/oai-pmh/v0/oai"
SIKT_SET         = "SIKT"
SIKT_MAX_RECORDS = 10000

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
    "cc-by", "cc by", "creative commons",
    "cc0", "cc-0", "public domain",
    "cc-by-sa", "cc-by-nc", "cc-by-nd",
    "cc-by-nc-sa", "cc-by-nc-nd",
    "odbl", "odc-by", "pddl",
    "mit", "apache", "gpl",
    "other-open", "other-at",
]

QUERIES_QDA = [
    "qdpx",
    "mqda",
    "refi-qda",
    "nvivo",
    "atlas.ti",
    "atlasti",
    "f4analyse",
    "quirkos",
    "qdaminer",
    "dedoose",
    "maxqda",
]
QUERIES_QUALITATIVE = [
    "interview study",
    "qualitative research data",
    "interview transcript",
    "focus group transcript",
    "thematic analysis data",
    "grounded theory interview",
    "qualitative content analysis",
    "ethnographic fieldnotes",
    "narrative inquiry data",
    "discourse analysis transcript",
    "oral history transcript",
    "qualitative longitudinal",
]

ALL_QUERIES = QUERIES_QDA + QUERIES_QUALITATIVE