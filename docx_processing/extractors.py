import re

AFFILIATION_KEYWORDS_RE = re.compile(
    r"\b(university|institute|department|dept\.?|faculty|academy|college|laboratory|centre|center)\b"
    r"|\b(університет|інститут|кафедра|факультет|академія|коледж|лабораторія|центр)\b",
    re.IGNORECASE,
)
# Top-level org (university / institute), not a department line used as its own <organization>.
INSTITUTION_TOP_LEVEL_RE = re.compile(
    r"\b(university|institute|academy|college|університет|інститут|академія|коледж)\b",
    re.IGNORECASE,
)
DEPARTMENT_LINE_RE = re.compile(
    r"^\s*(department|dept\.?|кафедра|faculty)\b",
    re.IGNORECASE,
)


def _looks_like_inline_author_line(text):
    if AFFILIATION_KEYWORDS_RE.search(text):
        return False
    if re.search(r",| and | та |\s&\s", text):
        return True
    return False


def _looks_like_sole_author_byline(text):
    """Single-author line without comma, e.g. 'P.I. Zamroz', 'I.V.Teleshko', or 'Zamroz P.I.'"""
    if not text or len(text) > 120:
        return False
    if AFFILIATION_KEYWORDS_RE.search(text):
        return False
    t = text.strip()
    if re.match(r"^([A-Za-zА-ЯІЇЄҐа-яіїєґ]\.){1,4}\s*[A-Za-zА-ЯІЇЄҐа-яіїєґ'\-]{2,}$", t):
        return True
    if re.match(
        r"^[A-Za-zА-ЯІЇЄҐа-яіїєґ'\-]{2,}\s+([A-Za-zА-ЯІЇЄҐа-яіїєґ]\.){1,4}$", t
    ):
        return True
    return False


def _looks_like_title_continuation(text):
    """Extra title line(s) split across paragraphs, e.g. 'FOR MOBILE AD HOC NETWORKS'."""
    if not text or len(text) > 220:
        return False
    if (
        AFFILIATION_KEYWORDS_RE.search(text)
        or _looks_like_sole_author_byline(text)
        or _looks_like_inline_author_line(text)
        or ORCID_LINE_RE.search(text)
        or SUBMISSION_META_RE.search(text)
        or EMAIL_RE.search(text)
    ):
        return False
    letters = re.sub(r"[^A-Za-z]", "", text)
    if len(letters) < 3:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio >= 0.8


EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
EMAIL_LABEL_RE = re.compile(
    r"\b([eе]-?mail|емейл)\b", re.IGNORECASE
)  # Latin e or Cyrillic е
ORCID_LINE_RE = re.compile(
    r"\bORCID\b|orcid\.org/|\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b",
    re.IGNORECASE,
)
ORCID_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?orcid\.org/(\d{4}-\d{4}-\d{4}-\d{3}[\dX])",
    re.IGNORECASE,
)
ORCID_ID_RE = re.compile(r"\b(\d{4}-\d{4}-\d{4}-\d{3}[\dX])\b", re.IGNORECASE)
SUBMISSION_META_RE = re.compile(
    r"\b(received|accepted|published)\s*:", re.IGNORECASE
)

# Temp: skip license lines between © and abstract (move license to bottom later).
LICENSE_LINES_TO_SKIP_AFTER_COPYRIGHT = 2


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
                if (
                    _looks_like_inline_author_line(text)
                    or _looks_like_sole_author_byline(text)
                    or _looks_like_title_continuation(text)
                ):
                    continue
            text = text.rstrip(" ,").strip()
            if text:
                out.append(text)
    return out


def affiliation_lines_for_crossref_organization(lines):
    """One Crossref <organization>: primary university/institute only (skip departments)."""
    cleaned = sanitize_affiliation_lines_for_organization(lines or [])
    if not cleaned:
        return []
    for text in cleaned:
        if INSTITUTION_TOP_LEVEL_RE.search(text) and not DEPARTMENT_LINE_RE.match(text):
            return [text]
    return [cleaned[0]]


def normalize_orcid_url(orcid_id):
    """Return a Crossref-compatible ORCID URL."""
    if not orcid_id:
        return None
    oid = orcid_id.strip()
    if oid.lower().startswith("http"):
        match = ORCID_URL_RE.search(oid)
        if match:
            return f"https://orcid.org/{match.group(1)}"
        match = ORCID_ID_RE.search(oid)
        if match:
            return f"https://orcid.org/{match.group(1)}"
        return None
    match = ORCID_ID_RE.search(oid)
    if match:
        return f"https://orcid.org/{match.group(1)}"
    return None


def extract_orcids_from_text(text):
    """Find ORCID identifiers in a line (URL, orcid.org/…, ORCID: …, or bare XXXX-XXXX-…)."""
    if not text:
        return []
    found = []
    seen = set()
    for match in ORCID_URL_RE.finditer(text):
        url = f"https://orcid.org/{match.group(1).upper()}"
        if url not in seen:
            seen.add(url)
            found.append(url)
    for match in ORCID_ID_RE.finditer(text):
        oid = match.group(1).upper()
        url = f"https://orcid.org/{oid}"
        if url not in seen:
            seen.add(url)
            found.append(url)
    return found


def _segment_is_orcid_only(segment):
    segment = (segment or "").strip()
    if not segment:
        return False
    without_label = re.sub(r"^ORCID\s*:\s*", "", segment, flags=re.IGNORECASE).strip()
    orcs = extract_orcids_from_text(without_label)
    if not orcs:
        return False
    remainder = without_label
    for match in ORCID_ID_RE.finditer(without_label):
        remainder = remainder.replace(match.group(0), "")
    remainder = re.sub(
        r"https?://(?:www\.)?orcid\.org/\d{4}-\d{4}-\d{4}-\d{3}[\dX]",
        "",
        remainder,
        flags=re.IGNORECASE,
    )
    return not re.search(r"[A-Za-zА-Яа-яІЇЄҐіїєґ]{2,}", remainder)


def _line_is_comma_separated_orcid_list(text):
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return False
    return all(_segment_is_orcid_only(p) for p in parts)


def extract_orcids_from_comma_separated_line(text):
    """One ORCID per comma-separated segment, preserving list order."""
    orcids = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        found = extract_orcids_from_text(part)
        if found:
            orcids.append(found[0])
    return orcids


def split_copyright_authors(authors_text):
    """Split ©-line authors on commas (same order as in the DOCX)."""
    if not authors_text or authors_text.strip() == "Authors not found.":
        return []
    text = re.sub(r"\s\d{4}$", "", authors_text.strip()).strip()
    return [part.strip() for part in text.split(",") if part.strip()]


def align_author_orcids(authors_text, raw_orcids):
    """Map extracted ORCIDs to copyright-line authors by position (1st→1st, etc.)."""
    authors = split_copyright_authors(authors_text)
    if not authors:
        return list(raw_orcids or [])
    aligned = []
    for i in range(len(authors)):
        aligned.append(raw_orcids[i] if raw_orcids and i < len(raw_orcids) else None)
    return aligned


def _english_header_lines_before_copyright(paragraphs, literature_references):
    """Paragraph lines between the English title block and the © line."""
    if not literature_references:
        return []
    try:
        last_index = paragraphs.index(literature_references[-1])
    except ValueError:
        return []
    title_idx = last_index + 1
    if title_idx >= len(paragraphs):
        return []

    j = title_idx + 1
    while j < len(paragraphs) and _looks_like_title_continuation(paragraphs[j]):
        j += 1

    lines = []
    while j < len(paragraphs):
        text = paragraphs[j]
        if text.startswith("©"):
            break
        lines.append(text)
        j += 1
    return lines


def extract_author_orcids(paragraphs, literature_references):
    """ORCID URLs from the English header (e.g. comma-separated list after e-mail)."""
    orcids = []
    seen = set()
    for line in _english_header_lines_before_copyright(paragraphs, literature_references):
        if _line_is_comma_separated_orcid_list(line):
            candidates = extract_orcids_from_comma_separated_line(line)
        else:
            candidates = extract_orcids_from_text(line)
        for url in candidates:
            if url not in seen:
                seen.add(url)
                orcids.append(url)
    return orcids


def _parse_english_header_after_literature(paragraphs, literature_references):
    """
    After the last literature reference: merge multi-line English title, then collect
    affiliation lines until © (skipping author byline(s)).
    Returns (english_title, affiliation_lines).
    """
    if not literature_references:
        return "English title not found.", []

    try:
        last_index = paragraphs.index(literature_references[-1])
    except ValueError:
        return "English title not found.", []

    title_idx = last_index + 1
    if title_idx >= len(paragraphs):
        return "English title not found.", []

    title_parts = [paragraphs[title_idx].strip()]
    j = title_idx + 1
    while j < len(paragraphs) and _looks_like_title_continuation(paragraphs[j]):
        title_parts.append(paragraphs[j].strip())
        j += 1

    between = []
    while j < len(paragraphs):
        text = paragraphs[j]
        if text.startswith("©"):
            break
        between.append(text)
        j += 1

    start = 0
    while start < len(between):
        line = between[start]
        if _looks_like_inline_author_line(line) or _looks_like_sole_author_byline(line):
            start += 1
            continue
        break

    affiliations = [line for line in between[start:] if line.strip()]
    return " ".join(title_parts), affiliations


def extract_affiliation_lines(paragraphs, literature_references):
    """Lines between the English title block and the copyright (©) line."""
    _, affiliations = _parse_english_header_after_literature(paragraphs, literature_references)
    return affiliations


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
    """Extracts the English title after the last literature reference (may span multiple lines)."""
    title, _ = _parse_english_header_after_literature(paragraphs, literature_references)
    return title

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
    """Extracts the abstract from the paragraphs (skips license lines after ©)."""
    abstract_text = "Abstract not found."
    abstract_start = None
    abstract_end = None
    for i, paragraph in enumerate(paragraphs):
        if re.match(r"^©", paragraph, re.IGNORECASE) and not re.search(
            r"[А-Яа-яІЇЄҐіїєґ]", paragraph
        ):
            abstract_start = i
            break
    if abstract_start is not None:
        start = abstract_start + 1 + LICENSE_LINES_TO_SKIP_AFTER_COPYRIGHT
        abstract_text = (
            "\n".join(paragraphs[start:abstract_end]).strip()
            if abstract_end
            else "\n".join(paragraphs[start:]).strip()
        )
    return abstract_text

