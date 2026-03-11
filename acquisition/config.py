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

ZENODO_MAX_PAGES = 100
ZENODO_PAGE_SIZE = 100

FSD_OAI_URL     = "https://services.fsd.tuni.fi/v0/oai"
FSD_MAX_RECORDS = 500

SIKT_OAI_URL     = "https://datacatalogue.cessda.eu/oai-pmh/v0/oai"
SIKT_SET         = "SIKT"
SIKT_MAX_RECORDS = 500

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

PRIMARY_EXTENSIONS = {
    ".txt", ".pdf", ".rtf", ".docx", ".doc",
    ".odt", ".md",  ".tex",
}

OPEN_LICENSE_KEYWORDS = [
    "cc-by", "cc by", "creative commons",
    "cc0", "cc-0", "public domain",
    "open access",
    "cc-by-sa", "cc-by-nc", "cc-by-nd",
    "cc-by-nc-sa", "cc-by-nc-nd",
    "mit", "apache", "gpl",
    "other-open", "other-at",
]

QUERIES_QDA = [
    "qdpx",              
    "refi-qda",          
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
    "interview study",               
    "qualitative research data",     
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