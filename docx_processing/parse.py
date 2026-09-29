import os
from docx import Document
import locale
from .page_count import get_page_count_from_metadata
from .styles import style_family, style_role


class StyledText(str):
    """Paragraph text that also carries its DOCX style metadata.

    Subclasses ``str`` so every text-based extractor, regex and join keeps
    working untouched, while style-aware code can consult ``.role`` / ``.style``.
    Note that ``str`` methods (``.strip()``, slicing, ...) return plain ``str``
    and drop the metadata, so paragraphs are stored already stripped.
    """

    __slots__ = ("style", "family", "role", "bold", "italic", "size")

    def __new__(cls, text, style="", bold=False, italic=False, size=None):
        obj = super().__new__(cls, text)
        obj.style = style or ""
        obj.family = style_family(style)
        obj.role = style_role(style)
        obj.bold = bold
        obj.italic = italic
        obj.size = size
        return obj


def _styled_paragraph(paragraph):
    """Wrap a python-docx paragraph as StyledText, capturing style and emphasis."""
    text = paragraph.text.strip()
    try:
        style_name = paragraph.style.name or ""
    except AttributeError:
        style_name = ""

    runs = [run for run in paragraph.runs if run.text and run.text.strip()]
    bold = any(run.bold for run in runs)
    italic = any(run.italic for run in runs)
    sizes = {run.font.size.pt for run in runs if run.font.size is not None}
    size = min(sizes) if sizes else None

    return StyledText(text, style=style_name, bold=bold, italic=italic, size=size)


def parse_docx(docx_path):
    """Parses the DOCX file and returns the list of paragraphs and page count.

    Paragraphs are StyledText instances, so downstream extractors can use either
    the text or the template style that tagged it.
    """
    document = Document(docx_path)
    paragraphs = [
        _styled_paragraph(para) for para in document.paragraphs if para.text.strip()
    ]

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
