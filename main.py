import os
import sys

import yaml
from docx_processing.article import ArticleRecord
from docx_processing.parse import process_multiple_docs
from docx_processing.styles import template_families
from docx_processing.extractors import (
    extract_ukrainian_title,
    extract_literature,
    extract_english_title,
    extract_authors,
    extract_abstract,
    extract_keywords,
    extract_affiliation_lines,
    extract_author_orcids,
    align_author_orcids,
)
from docx_validation.article_validator import (
    format_institution_stub,
    format_report,
    has_errors,
    unmapped_institutions,
    validate_articles,
)
from xml_generation.crossref.create_crossref_xml import create_full_xml
from xml_generation.ici_copernicus.create_copernicus_ini_xml import create_ici_copernicus_xml
from docx_generation.generate_docx import create_contents_docx, create_doi_letter_docx
from pdf_processing.page_count import extract_pdf_articles_pages
from pdf_processing.inject_pages import inject_pages_into_articles
with open("config.yml", "r") as f:
    config = yaml.safe_load(f)

DEFAULT_INPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "articles")
INPUT_FOLDER = config.get("app", {}).get("input_folder") or DEFAULT_INPUT_FOLDER
OUTPUT_FOLDER = config.get("app", {}).get("output_folder") or "output"

INSTITUTIONS_CONFIG = config.get("institutions") or {}
DEFAULT_INSTITUTION_ID = config.get("crossref", {}).get("default_institution")
FAIL_ON_ERROR = config.get("validation", {}).get("fail_on_error", True)


def extract_article(filename, paragraphs, start_page, end_page):
    """Build one ArticleRecord from a parsed DOCX."""
    literature = extract_literature(paragraphs)
    return ArticleRecord(
        filename=filename,
        english_title=extract_english_title(paragraphs, literature).upper(),
        ukrainian_title=extract_ukrainian_title(paragraphs).upper(),
        authors=extract_authors(paragraphs, False, literature),
        ukrainian_authors=extract_authors(paragraphs, True, literature),
        start_page=start_page,
        end_page=end_page,
        literature=literature,
        abstract=extract_abstract(paragraphs, literature),
        ukrainian_abstract=extract_abstract(paragraphs, literature, is_ukrainian=True),
        english_keywords=extract_keywords(paragraphs),
        ukrainian_keywords=extract_keywords(paragraphs, is_ukrainian=True),
        affiliation_lines=extract_affiliation_lines(paragraphs, literature),
        author_orcids=align_author_orcids(
            extract_authors(paragraphs, False, literature),
            extract_author_orcids(paragraphs, literature),
        ),
        template_families=template_families(paragraphs),
    )


def print_record(record):
    print(f"Processing file: {record.filename}")
    print("  Template styles:", ", ".join(record.template_families) or "none (plain text)")
    print("  Ukrainian Title:", record.ukrainian_title)
    print("  English Title:", record.english_title)
    print("  Authors:", record.authors)
    print("  Ukrainian Authors:", record.ukrainian_authors)
    print("  Abstract:", record.abstract)
    print("  Ukrainian Abstract:", record.ukrainian_abstract)
    print("  English Keywords:", ", ".join(record.english_keywords))
    print("  Ukrainian Keywords:", ", ".join(record.ukrainian_keywords))
    print("  Literature References:", len(record.literature))
    print("  affiliation_lines:", record.affiliation_lines)
    print("  author_orcids:", record.author_orcids)
    print(f"  Start Page: {record.start_page}, End Page: {record.end_page}")


if __name__ == '__main__':
    # The submissions folder changes every issue, so it is config (or argv[1]),
    # not a literal in the code.
    input_folder = sys.argv[1] if len(sys.argv) > 1 else INPUT_FOLDER
    print(f"Reading articles from: {input_folder}")

    records = []
    for filename, paragraphs, start_page, end_page in process_multiple_docs(input_folder):
        record = extract_article(filename, paragraphs, start_page, end_page)
        print_record(record)
        records.append(record)

    # Validate before anything is written: a malformed deposit is far more
    # expensive to undo at Crossref than to fix here.
    results = validate_articles(records, INSTITUTIONS_CONFIG, DEFAULT_INSTITUTION_ID)
    print(format_report(results, INSTITUTIONS_CONFIG))
    stub = format_institution_stub(unmapped_institutions(records, INSTITUTIONS_CONFIG))
    if stub:
        print(stub)

    if has_errors(results):
        print(
            "\nFix the errors above in the source DOCX and re-run. To deposit"
            " anyway, set `validation.fail_on_error: false` in config.yml."
        )
        if FAIL_ON_ERROR:
            print("No files were written.")
            sys.exit(1)

    articles_data = [record.to_tuple() for record in records]
    # not needed for XML forming, but used for the Ukrainian contents DOCX
    ukrainian_authors = [record.ukrainian_authors for record in records]

    if config["app"]["inject_pdf_pages"]:
        pages_pdf = extract_pdf_articles_pages("/Users/dmytro.kushnir/Library/CloudStorage/OneDrive-Personal/Lecturing/2026/журнал КСМ/Volume 8 number 1/документи/ЕТАП 7 Формування УДК та подача на DOI/VSE.pdf")
        articles_data = inject_pages_into_articles(articles_data, pages_pdf)

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    crossref_path = os.path.join(OUTPUT_FOLDER, "crossref.xml")
    copernicus_path = os.path.join(OUTPUT_FOLDER, "copernicus.xml")

    # Generate full XML for all articles
    with open(crossref_path, "w", encoding="utf-8") as f:
        f.write(create_full_xml(articles_data))

    with open(copernicus_path, "w", encoding="utf-8") as f:
        f.write(
            create_ici_copernicus_xml(
                articles_data, [record.language_payload() for record in records]
            )
        )

    # Create docx documents based on XML
    create_doi_letter_docx(crossref_path, os.path.join(OUTPUT_FOLDER, "doi_letter.docx"))
    create_contents_docx(crossref_path, os.path.join(OUTPUT_FOLDER, "contents_eng.docx"))
    create_contents_docx(
        crossref_path, os.path.join(OUTPUT_FOLDER, "contents_ua.docx"), ukrainian_authors
    )
    print(f"\nWrote XML and DOCX outputs to: {OUTPUT_FOLDER}")
