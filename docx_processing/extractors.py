import re

AFFILIATION_KEYWORDS_RE = re.compile(
    r"\b(university|institute|department|dept\.?|faculty|academy|college|laboratory|centre|center)\b"
    r"|\b(університет|інститут|кафедра|факультет|академія|коледж|лабораторія|центр)\b",
    re.IGNORECASE,
)


def _looks_like_inline_author_line(text):
    if AFFILIATION_KEYWORDS_RE.search(text):
        return False
    if re.search(r",| and | та |\s&\s", text):
        return True
    return False


def _looks_like_sole_author_byline(text):
    """Single-author line without comma, e.g. 'P.I. Zamroz' or 'Zamroz P.I.'"""
    if not text or len(text) > 120:
        return False
    if AFFILIATION_KEYWORDS_RE.search(text):
        return False
    t = text.strip()
    if re.match(r"^([A-Za-zА-ЯІЇЄҐа-яіїєґ]\.){1,3}\s+[A-Za-zА-ЯІЇЄҐа-яіїєґ'\-]{2,}$", t):
        return True
    if re.match(
        r"^[A-Za-zА-ЯІЇЄҐа-яіїєґ'\-]{2,}\s+([A-Za-zА-ЯІЇЄҐа-яіїєґ]\.){1,3}$", t
    ):
        return True
    return False


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
EMAIL_LABEL_RE = re.compile(
    r"\b([eе]-?mail|емейл)\b", re.IGNORECASE
)  # Latin e or Cyrillic е
ORCID_LINE_RE = re.compile(r"\bORCID\b|\b\d{4}-\d{4}-\d{4}-\d{4}\b", re.IGNORECASE)
SUBMISSION_META_RE = re.compile(
    r"\b(received|accepted|published)\s*:", re.IGNORECASE
)


def sanitize_affiliation_lines_for_organization(lines):
    """Keep only lines suitable for Crossref <organization> (drop email, ORCID, dates, author bylines)."""
    if not lines:
        return []
    out = []
    for raw in lines:
        for part in re.split(r"\n+", raw):
            text = part.strip()
            if not text:
                continue
            if EMAIL_RE.search(text) or EMAIL_LABEL_RE.search(text):
                continue
            if ORCID_LINE_RE.search(text):
                continue
            if SUBMISSION_META_RE.search(text):
                continue
            if not AFFILIATION_KEYWORDS_RE.search(text):
                if _looks_like_inline_author_line(text) or _looks_like_sole_author_byline(
                    text
                ):
                    continue
            text = text.rstrip(" ,").strip()
            if text:
                out.append(text)
    return out


def extract_affiliation_lines(paragraphs, literature_references):
    """Lines between the English title paragraph and the copyright (©) line, excluding a typical author-byline paragraph."""
    if not literature_references:
        return []
    try:
        last_index = paragraphs.index(literature_references[-1])
    except ValueError:
        return []
    title_idx = last_index + 1
    if title_idx >= len(paragraphs):
        return []

    between = []
    for j in range(title_idx + 1, len(paragraphs)):
        text = paragraphs[j]
        if text.startswith("©"):
            break
        between.append(text)

    if not between:
        return []

    start = 0
    if _looks_like_inline_author_line(between[0]):
        start = 1
    elif _looks_like_sole_author_byline(between[0]):
        start = 1

    return [line for line in between[start:] if line.strip()]


def extract_ukrainian_title(paragraphs):
    """Extracts the Ukrainian title, which is the paragraph after the one containing 'УДК'."""
    ukrainian_title = "Ukrainian title not found."
    for i, paragraph in enumerate(paragraphs):
        if "УДК" in paragraph:
            if i + 1 < len(paragraphs):
                ukrainian_title = paragraphs[i + 1]
            break
    return ukrainian_title

def extract_literature(paragraphs):
    """Extracts all literature references from the paragraphs."""
    literature_references = []
    found_literature = False
    for paragraph in paragraphs:
        if "Список літератури" in paragraph or re.search(r"\b(literature|references)\b", paragraph, re.IGNORECASE):
            found_literature = True
            continue
        if found_literature:
            # Check for a more flexible reference pattern
            if re.search(r"(doi:|vol\.|pp\.|\(\d{4}\)|\d{4}|Retrieved|http|https|Available:)", paragraph, re.IGNORECASE):
                literature_references.append(paragraph)
            else:
                # Stop if no longer in the literature section
                break
    return literature_references

def extract_english_title(paragraphs, literature_references):
    """Extracts the English title, which is the paragraph after the last literature reference."""
    english_title = "English title not found."
    if literature_references:
        last_reference = literature_references[-1]
        last_index = paragraphs.index(last_reference)
        if last_index + 1 < len(paragraphs):
            english_title = paragraphs[last_index + 1]
    return english_title

def extract_authors(paragraphs, is_ukrainian=False):
    """Extracts authors' names from the paragraphs.

    :param paragraphs: List of paragraphs from the DOCX file.
    :param is_ukrainian: Boolean flag indicating whether the text is in Ukrainian.
    :return: Extracted authors' names.
    """
    authors_text = "Authors not found."

    for paragraph in paragraphs:
        if paragraph.startswith("©"):
            # If extracting English authors, ensure no Cyrillic characters
            if not is_ukrainian and re.search(r"[А-Яа-яІЇЄҐіїєґ]", paragraph):
                continue  # Skip this paragraph as it contains Cyrillic

            # Extract authors after '©' and clean year if present
            authors_text = paragraph[1:].strip()
            authors_text = re.sub(r"\s\d{4}$", "", authors_text).strip()
            break

    return authors_text

def extract_abstract(paragraphs):
    """Extracts the abstract from the paragraphs."""
    abstract_text = "Abstract not found."
    abstract_start = None
    abstract_end = None
    for i, paragraph in enumerate(paragraphs):
        # Check if the paragraph starts with "©" and contains only Latin characters
        if re.match(r"^©", paragraph, re.IGNORECASE) and not re.search(r"[А-Яа-яІЇЄҐіїєґ]", paragraph):
            abstract_start = i
            break
    if abstract_start is not None:
        abstract_text = "\n".join(paragraphs[abstract_start + 1:abstract_end]).strip() if abstract_end else "\n".join(paragraphs[abstract_start + 1:]).strip()
    return abstract_text

