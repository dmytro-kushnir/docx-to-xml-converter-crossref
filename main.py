from docx_processing.parse import process_multiple_docs
from docx_processing.extractors import (
    extract_ukrainian_title,
    extract_literature,
    extract_english_title,
    extract_authors,
    extract_abstract,
)
from xml_generation.create_xml import create_full_xml
from docx_generation.generate import create_docx_with_xml

if __name__ == '__main__':
    all_docs = process_multiple_docs("articles")
    articles_data = []
    for filename, paragraphs, start_page, end_page in all_docs:
        print(f"Processing file: {filename}")

        # Extract the information
        ukrainian_title = extract_ukrainian_title(paragraphs).upper()
        literature_references = extract_literature(paragraphs)
        english_title = extract_english_title(paragraphs, literature_references).upper()
        authors_text = extract_authors(paragraphs)
        abstract_text = extract_abstract(paragraphs)

        # Print the extracted information
        print("Ukrainian Title:", ukrainian_title)
        print("English Title:", english_title)
        print("Authors:", authors_text)
        print("Abstract:", abstract_text)
        print("Literature References:", literature_references)
        print(f"Start Page: {start_page}, End Page: {end_page}")

        # Prepare data for full XML generation
        articles_data.append((english_title, ukrainian_title, authors_text, (start_page, end_page), literature_references, abstract_text))

    # Generate full XML for all articles
    xml_output = create_full_xml(articles_data)
    xml_output_name = "output/crossref.xml"
    with open(xml_output_name, "w", encoding="utf-8") as f:
        f.write(xml_output)

    # Create docx document based on XML
    create_docx_with_xml(xml_output_name, "output/doi_letter.docx")