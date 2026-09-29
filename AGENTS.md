# Agent Guide: docx-to-xml-converter-crossref

## What this project does
Converts batches of academic DOCX articles (Ukrainian/English) into:
- Crossref XML for DOI registration
- ICI Copernicus XML
- DOCX artifacts (DOI letter, contents in EN/UA)

## Primary entry point
- `main.py` orchestrates the pipeline:
  1. Parse DOCX files and extract metadata into `ArticleRecord`s
  2. Validate every record and refuse to write on any ERROR
  3. Optionally inject page numbers from a PDF
  4. Generate Crossref and Copernicus XML
  5. Generate DOCX outputs from XML
- Run as `python main.py` (uses `app.input_folder`) or `python main.py /path/to/folder`.

## Key folders and responsibilities
- `docx_processing/`: parse DOCX, extract titles/authors/abstract/keywords/literature, count pages
  - `styles.py`: maps DOCX paragraph style names (`CSN:`, `CSN SOT:`, `ACPS:`, Word built-ins) to semantic roles. Extraction consults these roles **first** and only falls back to text heuristics for untemplated documents; a byline and the CC-BY notice are both Latin `©` paragraphs, and only the style separates them.
  - `article.py`: `ArticleRecord`, the named form of one article. `to_tuple()` is the boundary to the XML generators; `language_payload()` carries the per-language text Copernicus needs.
- `pdf_processing/`: derive page numbers from a PDF and inject into article data
- `xml_generation/crossref/`: build Crossref XML (authors, pages, literature, URL slugs)
- `xml_generation/ici_copernicus/`: build ICI Copernicus XML
- `docx_generation/`: build DOI letter and contents DOCX from XML
- `docx_validation/`:
  - `article_validator.py`: pre-flight gate over the extracted records (wired into `main.py`)
  - `title_sequence_validator.py`: checks section sequence in DOCX (not wired into main flow)
- `gsheet_integration/`: Google Sheets append helpers (currently unused in `main.py`)
- `pdf_generation/`: DOCX->PDF and merge utilities (not used in main flow)

## Inputs and outputs
- Input DOCX folder comes from `config.yml` → `app.input_folder` (or `argv[1]`); defaults to `articles/`
- Config in `config.yml` (journal metadata, DOI prefix, institutions/ROR, validation, PDF injection toggle)
- Outputs written to `app.output_folder` (default `output/`):
  - `crossref.xml`
  - `copernicus.xml`
  - `doi_letter.docx`
  - `contents_eng.docx`
  - `contents_ua.docx`

## Data model (high level)
Extraction produces an `ArticleRecord` (`docx_processing/article.py`). At the XML boundary
`to_tuple()` yields the positional form the generators expect:
`(english_title, ukrainian_title, authors_text, (start_page, end_page), literature_refs, abstract_text, affiliation_lines, author_orcids)`
- `affiliation_lines`: `list[str]` between the English title and `©` (excluding a typical byline). Crossref 5.4.0 maps the primary university to ROR `<affiliations>` on each `<person_name>` (`config.yml` → `institutions`). ICI Copernicus uses full sanitized lines (`item[:6]`).
- Copernicus also needs the Ukrainian abstract and both keyword lists. These are passed
  **alongside** the tuples as `language_payloads`, not appended to them, because
  `pdf_processing/inject_pages.py` rewrites the tuples and drops anything past index 7.
DOI letter / contents are built from the generated `crossref.xml` via `docx_generation/generate_docx.py`.

## Validation gate
`docx_validation/article_validator.py` runs before anything is written:
- `ERROR` — would deposit wrong or placeholder metadata (missing/boilerplate title or byline,
  a Cyrillic English title, licence text parsed as authors, an affiliation that would silently
  inherit another university's ROR). Blocks the write when `validation.fail_on_error: true`.
- `WARNING` — needs a human look but is often a real gap in the source (an author with no ORCID).
  Never blocks. **Page findings are always warnings**: page ranges stay provisional until the
  typeset PDF exists.
Unmapped affiliations are reported as a paste-ready `institutions:` YAML stub. Never invent a
ROR identifier — leave `ror: ""` for a human to fill in.

There is deliberately **no per-article override mechanism**: when a document cannot be parsed,
the fix belongs in the source DOCX, not in config.

## Important constraints and cautions
- PDF page injection relies on a marker phrase in the PDF; verify matching text.
- The PDF path in `main.py` is still a literal and is only read when `app.inject_pdf_pages` is true.
- File ordering uses Ukrainian alphabet sorting in `docx_processing/parse.py`.
- `service_account.json` contains credentials; treat as sensitive.

## When changing behavior
- Keep XML schemas valid (Crossref 5.4.0 + ROR affiliations, ICI Copernicus).
- Update both EN/UA flows when changing title/author parsing.
- If you modify extraction logic, verify downstream XML/DOCX generators.
- Keep logic issue-agnostic: the article set changes every issue, so drive behaviour from
  paragraph styles, patterns, and config — never from a specific author, title, or filename.
- Author names are parsed in one place, `xml_generation/crossref/create_authors.py:parse_author_name`,
  so Crossref and Copernicus always credit identical names.
- Run `python -m pytest` — the extraction tiers, name parsing, validator, and both XML
  generators are covered under `tests/`.
