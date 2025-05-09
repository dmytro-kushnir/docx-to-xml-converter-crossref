import yaml
from docx_processing.parse import process_multiple_docs
from docx_processing.extractors import (
    extract_ukrainian_title,
    extract_literature,
    extract_english_title,
    extract_authors,
    extract_abstract,
)
from xml_generation.create_xml import create_full_xml
from docx_generation.generate_docx import create_contents_docx, create_doi_letter_docx
from pdf_processing.page_count import extract_pdf_articles_pages
from pdf_processing.inject_pages import inject_pages_into_articles

with open("config.yml", "r") as config_file:
    INJECT_PAGES_FROM_PDF = yaml.safe_load(config_file)["app"]["inject_pdf_pages"]

if __name__ == '__main__':
    input_folder=""
    all_docs = process_multiple_docs(input_folder)
    articles_data = []
    ukrainian_authors = [] # not needed for XML forming, but may be useful for other features
    for filename, paragraphs, start_page, end_page in all_docs:
        print(f"Processing file: {filename}")

        # Extract the information
        ukrainian_title = extract_ukrainian_title(paragraphs).upper()
        literature_references = extract_literature(paragraphs)
        english_title = extract_english_title(paragraphs, literature_references).upper()
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
        print(f"Start Page: {start_page}, End Page: {end_page}")

        # Prepare data for full XML generation
        articles_data.append((english_title, ukrainian_title, authors_text, (start_page, end_page), literature_references, abstract_text))

    if INJECT_PAGES_FROM_PDF:
        pages_pdf = extract_pdf_articles_pages("")
        articles_data = inject_pages_into_articles(articles_data, pages_pdf)

    # Generate full XML for all articles
    xml_output = create_full_xml(articles_data)
    xml_output_name = "output/crossref.xml"
    with open(xml_output_name, "w", encoding="utf-8") as f:
        f.write(xml_output)

    # Create docx documents based on XML
    create_doi_letter_docx(xml_output_name, "output/doi_letter.docx")
    create_contents_docx(xml_output_name, "output/contents_eng.docx")
    create_contents_docx(xml_output_name, "output/contents_ua.docx", ukrainian_authors)