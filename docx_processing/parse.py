import os
from docx import Document
import locale
from .page_count import get_page_count_from_metadata

def parse_docx(docx_path):
    """Parses the DOCX file and returns the document object, list of paragraphs, and page count."""
    document = Document(docx_path)
    paragraphs = [para.text.strip() for para in document.paragraphs if para.text.strip()]

    # Count the number of explicit page breaks, add 1 for the initial page
    page_count = get_page_count_from_metadata(docx_path)

    return paragraphs, page_count

# Define Ukrainian alphabet for custom sorting
UKRAINIAN_ALPHABET = "АаБбВвГгҐґДдЕеЄєЖжЗзИиІіЇїЙйКкЛлМмНнОоПпРрСсТтУуФфХхЦцЧчШшЩщЬьЮюЯя"

# Create a mapping from each character to its position in the Ukrainian alphabet
alphabet_order = {char: index for index, char in enumerate(UKRAINIAN_ALPHABET)}

def ukrainian_sort_key(filename):
    """Generate a sort key for Ukrainian filenames."""
    # Replace each character with its position in the alphabet, or a high value if not found
    return [alphabet_order.get(char, len(UKRAINIAN_ALPHABET)) for char in filename]

def process_multiple_docs(directory_path):
    """Processes multiple DOCX files in the given directory."""
    all_paragraphs = []
    current_page = 1

    # Get the list of files in the directory and sort them using the Ukrainian sorting key
    filenames = sorted([f for f in os.listdir(directory_path) if f.endswith(".docx")], key=ukrainian_sort_key)

    for filename in filenames:
        if filename.endswith(".docx"):
            docx_path = os.path.join(directory_path, filename)
            paragraphs, page_count = parse_docx(docx_path)
            start_page = current_page
            end_page = current_page + page_count - 1
            current_page = end_page + 1
            all_paragraphs.append((filename, paragraphs, start_page, end_page))

    return all_paragraphs
