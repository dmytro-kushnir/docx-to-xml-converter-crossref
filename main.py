import os
import yaml
from docx_processing.parse import process_multiple_docs
from docx_processing.extractors import (
    extract_ukrainian_title,
    extract_literature,
    extract_english_title,
    extract_authors,
    extract_abstract,
    extract_affiliation_lines,
)
from xml_generation.crossref.create_crossref_xml import create_full_xml
from xml_generation.ici_copernicus.create_copernicus_ini_xml import create_ici_copernicus_xml
from docx_generation.generate_docx import create_contents_docx, create_doi_letter_docx
from pdf_processing.page_count import extract_pdf_articles_pages
from pdf_processing.inject_pages import inject_pages_into_articles
with open("config.yml", "r") as f:
    config = yaml.safe_load(f)


if __name__ == '__main__':
    input_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "articles")
    all_docs = process_multiple_docs(input_folder)
    articles_data = []
    ukrainian_authors = [] # not needed for XML forming, but may be useful for other features

    for filename, paragraphs, start_page, end_page in all_docs:
        print(f"Processing file: {filename}")

        # Extract the information
        ukrainian_title = extract_ukrainian_title(paragraphs).upper()
        literature_references = extract_literature(paragraphs)
        english_title = extract_english_title(paragraphs, literature_references).upper()
        affiliation_lines = extract_affiliation_lines(paragraphs, literature_references)
        authors_text = extract_authors(paragraphs)
        authors_ukrainian_text = extract_authors(paragraphs, True)
        ukrainian_authors.append(authors_ukrainian_text)
        abstract_text = extract_abstract(paragraphs)

        # Print the extracted information
        print("Ukrainian Title:", ukrainian_title)
        print("English Title:", english_title)
        print("Authors:", authors_text)
        print("Ukrainian Authors:", authors_ukrainian_text)
        print("Abstract:", abstract_text)
        print("Literature References:", literature_references)
        print("affiliation_lines:", affiliation_lines)
        print(f"Start Page: {start_page}, End Page: {end_page}")

        # Prepare data for full XML generation
        articles_data.append(
            (
                english_title,
                ukrainian_title,
                authors_text,
                (start_page, end_page),
                literature_references,
                abstract_text,
                filename,
                affiliation_lines,
            )
        )

    if config["app"]["inject_pdf_pages"]:
        pages_pdf = extract_pdf_articles_pages("")
        articles_data = inject_pages_into_articles(articles_data, pages_pdf)

    # Generate full XML for all articles
    with open("output/crossref.xml", "w", encoding="utf-8") as f:
        f.write(create_full_xml(articles_data))

    with open("output/copernicus.xml", "w", encoding="utf-8") as f:
        f.write(create_ici_copernicus_xml(articles_data))

    # Create docx documents based on XML
    create_doi_letter_docx("output/crossref.xml", "output/doi_letter.docx")
    create_contents_docx("output/crossref.xml", "output/contents_eng.docx")
    create_contents_docx("output/crossref.xml", "output/contents_ua.docx", ukrainian_authors)