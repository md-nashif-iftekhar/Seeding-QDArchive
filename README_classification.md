# Part 2: Classification — Seeding QDArchive
**Repositories assigned:** #11 FSD (Finnish Social Science Data Archive), #20 Sikt (Norwegian data archive)

---

## Overview

The qualitative research datasets obtained in Part 1 (data acquisition) are categorised using two dimensions:

Depending on the files a project contains, the project type can be QDA_PROJECT, QD_PROJECT, OTHER_PROJECT, or NOT_A_PROJECT.

The research domain is categorised to division level (for example, Q85 Education) utilising both metadata (Tier 1) and primary data file contents (Tier 2) in the ISIC Rev. 5 classification.

### Key Features
- **Project Typing**: Classifies each project by the kind of files it contains
- **ISIC Rev. 5 Classification**: Assigns a research domain (division level, e.g. `Q85`)
- **Two-Tier Base Data**: Uses metadata (Tier 1) and actual file contents (Tier 2)
- **QDA Extraction**: Unzips QDA/ZIP archives to read the primary data inside
- **Structured Output**: Updates the SQLite database and exports XLSX + PDF deliverables

### Architecture Overview

The pipeline consists of four main phases:

1. **Mapping Phase**: Mapping he ISIC Rev. 5 keywords
2. **Typing Phase**: Classify each project's type from its file extensions
3. **Classification Phase**: Assign an ISIC class using Tier 1 (metadata) + Tier 2 (file contents)
4. **Output Phase**: Export the results table (XLSX) and the report (PDF)

## Project Structure

```
Seeding-QDArchive/
├── 23240175-seeding.db                 # Database from Part 1 (with type + class added)
├── 23240175-sq26-classification.db     # Classification database
├── classification/                     # Classification
│   ├── README_classification.md        # About the project
│   ├── keywords_mapping.py             # ISIC divisions + keyword mapping
│   ├── isic_keywords_map.json          # Generated keyword map
│   ├── update_db.py                    # Adds type + Tier 1 class columns
│   ├── classify.py                     # Tier 1 + Tier 2 ISIC classification
│   ├── result.py                       # Exports results table (XLSX)
│   ├── 23240175-sq26-results.xlsx      # Results table
└── acquisition/
    └── archive/                        # Downloaded data (read for Tier 2)
```

---

## Setup

### Prerequisites
- **Python**: 3.10 or higher
- **System**: Windows/Linux/macOS
- **Part 1 archive**: `acquisition/archive/` must be present for Tier 2 content reading

### Installation

1. **Navigate and activate the environment**:
```bash
cd Seeding-QDArchive
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

2. **Install dependencies**:
```bash
pip install openpyxl pypdf matplotlib reportlab svglib
```

---

## Running the Pipeline

Run from the `classification/` folder:

# Step 1: Keyword mapping builder
```bash
python keywords_mapping.py
```
# Step 2: Add type and Tier 1 class columns to the database
```bash
python update_db.py
```
# Step 3: Tier 1 and Tier 2 classification (reads actual file contents)
```bash
python classify.py
```
# Step 4: Export the results table (XLSX)
```bash
python result.py
```

---

## Technical Challenges

### FSD — Restricted access
Only Condition A datasets (CC BY 4.0) were openly downloadable; the remaining datasets require individual access applications per dataset. Of the datasets identified across both repositories, only a small fraction had downloadable primary data files, so most projects are classified `NOT_A_PROJECT` for lack of derivable file types.

### Sikt — Quantitative focus
Sikt is mostly focused on quantitative survey data, qualitative holdings are less. Qualitative datasets always contain personal information and are protected by a data processing agreement because Sikt's deposit policy prohibits the acceptance of anonymised qualitative data. As a result, only study documentation and survey tools (questionnaires, opinion polls) were freely downloadable, interview transcripts were not. This obstacle is structural rather than technical.

### Language
Tier 1 categorisation is effective because the metadata is bilingual (fi/en, no/en). 
To let Tier 2 contribute meaningfully, the ISIC keyword map was extended with Finnish and Norwegian terms for the divisions present in the data (e.g. koulutus/utdanning → Education, työ/arbeid → Employment, politiikka/valg → Public administration).

### Accessibility as a finding
Only a small percentage of the datasets that were found had files that could be downloaded.