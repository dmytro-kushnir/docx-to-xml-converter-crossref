# Agent Guide: docx-to-xml-converter-crossref

## What this project does
Converts batches of academic DOCX articles (Ukrainian/English) into:
- Crossref XML for DOI registration
- ICI Copernicus XML
- DOCX artifacts (DOI letter, contents in EN/UA)

## Primary entry point
- `main.py` orchestrates the pipeline:
  1. Parse DOCX files and extract metadata
  2. Optionally inject page numbers from a PDF
  3. Generate Crossref and Copernicus XML
  4. Generate DOCX outputs from XML

## Key folders and responsibilities
- `docx_processing/`: parse DOCX, extract titles/authors/abstract/literature, count pages
- `pdf_processing/`: derive page numbers from a PDF and inject into article data
- `xml_generation/crossref/`: build Crossref XML (authors, pages, literature, URL slugs)
- `xml_generation/ici_copernicus/`: build ICI Copernicus XML
- `docx_generation/`: build DOI letter and contents DOCX from XML
- `docx_validation/`: checks section sequence in DOCX (not wired into main flow)
- `gsheet_integration/`: Google Sheets append helpers (currently unused in `main.py`)
- `pdf_generation/`: DOCX->PDF and merge utilities (not used in main flow)

## Inputs and outputs
- Input DOCX files live in `articles/`
- Config in `config.yml` (journal metadata, DOI prefix, PDF injection toggle)
- Outputs written to `output/`:
  - `crossref.xml`
  - `copernicus.xml`
  - `doi_letter.docx`
  - `contents_eng.docx`
  - `contents_ua.docx`

## Data model (high level)
Each article becomes a tuple/list of:
`(english_title, ukrainian_title, authors_text, (start_page, end_page), literature_refs, abstract_text)`
This structure is passed into XML and DOCX generators.

## Important constraints and cautions
- PDF page injection relies on a marker phrase in the PDF; verify matching text.
- File ordering uses Ukrainian alphabet sorting in `docx_processing/parse.py`.
- `service_account.json` contains credentials; treat as sensitive.
- `main.py` uses some hardcoded paths; update carefully.

## When changing behavior
- Keep XML schemas valid (Crossref 4.4.2, ICI Copernicus).
- Update both EN/UA flows when changing title/author parsing.
- If you modify extraction logic, verify downstream XML/DOCX generators.
