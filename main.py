import re
from docx import Document
import xml.etree.ElementTree as ET

def parse_docx_to_paragraphs(docx_path):
    """Parses the DOCX file and returns a list of paragraphs."""
    document = Document(docx_path)
    paragraphs = [para.text.strip() for para in document.paragraphs if para.text.strip()]
    return paragraphs

def extract_authors(paragraphs):
    """Extracts authors' names from the paragraphs."""
    authors_text = "Authors not found."

    # Iterate through paragraphs to find the one that starts with © and contains Latin letters only (no Cyrillic)
    for paragraph in paragraphs:
        if paragraph.startswith("©") and not re.search(r"[А-Яа-яІЇЄҐіїєґ]", paragraph):
            # Remove the © symbol and any trailing year
            authors_text = paragraph[1:].strip()  # Remove the © and leading space
            # Remove the trailing year, if present (4-digit number at the end)
            authors_text = re.sub(r"\s\d{4}$", "", authors_text).strip()
            break

    return authors_text

def extract_abstract(paragraphs):
    """Extracts the abstract from the paragraphs."""
    abstract_text = "Abstract not found."

    # Assume the abstract follows a certain structure or section heading, e.g., after "Abstract" or before "Introduction"
    abstract_start = None
    abstract_end = None

    for i, paragraph in enumerate(paragraphs):
        if re.match(r"^©", paragraph, re.IGNORECASE):
            abstract_start = i
        elif re.match(r"^Вступ|Introduction", paragraph, re.IGNORECASE) and abstract_start is not None:
            abstract_end = i
            break

    if abstract_start is not None:
        abstract_text = "\n".join(paragraphs[abstract_start + 1:abstract_end]).strip() if abstract_end else "\n".join(paragraphs[abstract_start + 1:]).strip()

    return abstract_text

def create_xml_for_authors(authors_text):
    """Converts extracted authors into XML format."""
    # Split authors by comma and strip whitespace
    authors_list = [author.strip() for author in authors_text.split(",")]

    # XML root element
    root = ET.Element("authors")

    # Process each author
    for author in authors_list:
        # Split into surname and given_name (e.g., "Vovchak O.")
        name_parts = author.split()
        surname = name_parts[0]
        given_name = name_parts[1] if len(name_parts) > 1 else ""

        # XML element for each author
        person_name = ET.SubElement(root, "person_name", sequence="additional", contributor_role="author")
        ET.SubElement(person_name, "given_name").text = given_name
        ET.SubElement(person_name, "surname").text = surname

    # Convert to XML string (for display purposes)
    xml_str = ET.tostring(root, encoding="unicode")
    return xml_str


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    docx_path = "Грицько.docx"
    # Parse the document to paragraphs
    paragraphs = parse_docx_to_paragraphs(docx_path)

    authors_text = extract_authors(paragraphs)
    print("Authors:", authors_text)

    abstract_text = extract_abstract(paragraphs)
    print("Abstract:", abstract_text)

    xml_output = create_xml_for_authors(authors_text)
    print(xml_output)
