import re
from collections import namedtuple

from .styles import paragraph_role, paragraphs_with_role

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
CYRILLIC_RE = re.compile(r"[А-Яа-яІЇЄҐіїєґ]")


def _has_cyrillic(text):
    return bool(CYRILLIC_RE.search(text or ""))


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


def _looks_like_full_name_byline(text):
    """Byline written out in full rather than as initials, e.g. 'Yuriy Klushyn'."""
    if not text or len(text) > 60:
        return False
    if AFFILIATION_KEYWORDS_RE.search(text) or EMAIL_RE.search(text):
        return False
    words = text.strip().rstrip(",").split()
    if not 2 <= len(words) <= 4:
        return False
    return all(
        len(word) >= 2 and word[0].isalpha() and word[0].isupper() for word in words
    )


def looks_like_uppercase_title(text):
    """Mostly-uppercase heading line in either script (used to find a title)."""
    if not text or len(text) > 300:
        return False
    if (
        KEYWORDS_LINE_RE.match(text)
        or ORCID_LINE_RE.search(text)
        or SUBMISSION_META_RE.search(text)
        or EMAIL_RE.search(text)
        or LICENSE_NOTICE_RE.search(text)
        or starts_with_copyright(text)
    ):
        return False
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 8:
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
    r"\b(received|accepted|published)\s*:"
    r"|надійшла\s+до\s+редакції"
    r"|прийнят[аo]\s+до\s+друку"
    r"|опубліковано\s*:",
    re.IGNORECASE,
)

# CC-BY / licence boilerplate. Several templates place this notice in a plain
# ``Normal`` paragraph that also starts with "(c)", so it must never be mistaken
# for the author copyright byline.
LICENSE_NOTICE_RE = re.compile(
    r"the\s+author\(s\)"
    r"|open\s+access"
    r"|creative\s*commons"
    r"|creativecommons\.org"
    r"|\bcc\s*by\b"
    r"|licen[sc]ed?\s+under"
    r"|distributed\s+under"
    r"|this\s+article\s+is\s+licensed"
    r"|стаття\s+поширюється"
    r"|ліценз",
    re.IGNORECASE,
)

# "(c)" optionally preceded by hand-typed emphasis or bracket decoration, so
# '*(c) Zhuravchak Yu. Yu., 2026*' is recognised as the byline it is.
COPYRIGHT_PREFIX_RE = re.compile(r"^[\s*_«\"'\[(]*©\s*")


def starts_with_copyright(text):
    return bool(COPYRIGHT_PREFIX_RE.match(text or ""))

KEYWORDS_LINE_RE = re.compile(
    r"^\s*(key\s*words|keywords|ключові\s+слова)\s*[:.]",
    re.IGNORECASE,
)
# The label itself identifies the language, which is more reliable than the
# script of the terms: Ukrainian keyword lines are full of Latin technical terms.
ENGLISH_KEYWORDS_LABEL_RE = re.compile(r"^\s*key\s*words\s*[:.]\s*", re.IGNORECASE)
UKRAINIAN_KEYWORDS_LABEL_RE = re.compile(
    r"^\s*ключові\s+слова\s*[:.]\s*", re.IGNORECASE
)
# Numbered section heading ("1. Вступ", "2.1 Related work"), the boundary an
# abstract must never cross when the keywords line is missing. Tokens may not
# contain a period, so a numbered reference entry is not mistaken for a heading.
SECTION_HEADING_RE = re.compile(
    r"^\s*\d+(?:\.\d+)*\s*[.)]\s*[^\s.]+(?:\s+[^\s.]+){0,5}\s*$"
)
ABSTRACT_LABEL_RE = re.compile(
    r"^\s*(abstract|annotation|анотація)\s*[:.]\s*",
    re.IGNORECASE,
)
# The same word on a line of its own, used as a section heading with the
# abstract body in the following paragraph(s).
ABSTRACT_HEADING_RE = re.compile(
    r"^\s*(abstract|annotation|анотація)\s*[:.]?\s*$",
    re.IGNORECASE,
)

# Standalone reference-list heading. Anchored end-to-end so that section
# headings ("Literature Review") and prose that merely mentions the word do not
# match — that false-positive silently truncated reference lists to nothing.
REFERENCE_HEADING_RE = re.compile(
    r"^\s*\d{0,2}\s*[.)]?\s*("
    r"список\s+(використаних\s+)?(літератури|джерел)"
    r"|перелік\s+(використаних\s+)?(джерел|літератури)"
    r"|використані\s+джерела"
    r"|література"
    r"|references?"
    r"|reference\s+list"
    r"|bibliography"
    r")\s*:?\s*$",
    re.IGNORECASE,
)
REFERENCE_ENTRY_RE = re.compile(
    r"^\s*\[?\d{1,3}[\].)]"
    r"|doi:|doi\.org|\bvol\.|\bno\.|\bpp?\.|\(\d{4}\)|\b(19|20)\d{2}\b"
    r"|https?://|retrieved|available|url:|режим\s+доступу|електронний\s+ресурс",
    re.IGNORECASE,
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
            if LICENSE_NOTICE_RE.search(text):
                continue
            if not AFFILIATION_KEYWORDS_RE.search(text):
                if (
                    _looks_like_inline_author_line(text)
                    or _looks_like_sole_author_byline(text)
                    or _looks_like_title_continuation(text)
                ):
                    continue
            # Drop template noise that would otherwise land inside <organization>.
            text = re.sub(
                r"^\s*(corresponding\s+authors?|автор\s+для\s+кореспонденції)\s*:?\s*",
                "",
                text,
                flags=re.IGNORECASE,
            )
            text = re.sub(r"^\s*\d+\s*(?=[A-Za-zА-ЯІЇЄҐ])", "", text)
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


def affiliation_department_for_crossref(lines):
    """Optional department line from header affiliations (for institution_department)."""
    for text in sanitize_affiliation_lines_for_organization(lines or []):
        if DEPARTMENT_LINE_RE.match(text):
            return text
    return None


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


def _strip_copyright_decoration(text):
    """'© Hrytsko T.L., Hlukhov V.S. 2026' -> 'Hrytsko T.L., Hlukhov V.S.'"""
    # Some bylines are wrapped in emphasis markers typed by hand ('*© ... 2026*').
    cleaned = (text or "").strip().strip("*_").strip()
    cleaned = COPYRIGHT_PREFIX_RE.sub("", cleaned).strip()
    # Trailing year, with or without a separating comma.
    cleaned = re.sub(r"[\s,]*\b\d{4}\b\s*$", "", cleaned).strip().rstrip(",").strip()
    # Affiliation footnote markers glued to a surname ('Petriv1' -> 'Petriv').
    return re.sub(
        r"(?<=[A-Za-zА-Яа-яІЇЄҐіїєґ'])\d+(?=[\s,]|$)", "", cleaned
    ).strip()


def split_copyright_authors(authors_text):
    """Split ©-line authors on commas (same order as in the DOCX)."""
    if not authors_text or authors_text.strip() == "Authors not found.":
        return []
    text = _strip_copyright_decoration(authors_text)
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


def _copyright_byline_indices(paragraphs):
    """Indexes of ©-lines that are author bylines rather than licence notices.

    The copyright *style* cannot be used as a gate: templates reuse it for the
    licence block and even for the keywords line, and some documents style only
    the Ukrainian byline while leaving the English one as plain text. Requiring
    the "(c)" prefix and rejecting licence boilerplate is what actually
    discriminates.
    """
    return [
        i
        for i, paragraph in enumerate(paragraphs)
        if starts_with_copyright(paragraph)
        and not LICENSE_NOTICE_RE.search(paragraph)
    ]


def _last_reference_index(paragraphs, literature_references):
    if not literature_references:
        return None
    try:
        return paragraphs.index(literature_references[-1])
    except ValueError:
        return None


def _paragraphs_after_last_reference(paragraphs, literature_references):
    index = _last_reference_index(paragraphs, literature_references)
    if index is None:
        return []
    return list(paragraphs[index + 1 :])


def _orcids_from_lines(lines):
    """ORCID URLs found in the given lines, de-duplicated, order preserved."""
    orcids = []
    seen = set()
    for line in lines:
        if _line_is_comma_separated_orcid_list(line):
            candidates = extract_orcids_from_comma_separated_line(line)
        else:
            candidates = extract_orcids_from_text(line)
        for url in candidates:
            if url not in seen:
                seen.add(url)
                orcids.append(url)
    return orcids


def _english_header_lines_before_copyright(paragraphs, literature_references):
    """Paragraph lines between the English title block and the © line."""
    if not literature_references:
        return []
    last_index = _last_reference_index(paragraphs, literature_references)
    if last_index is None:
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
        if starts_with_copyright(text):
            break
        lines.append(text)
        j += 1
    return lines


def extract_author_orcids(paragraphs, literature_references):
    """ORCID URLs for the article's authors, in author order.

    Searched in order of trustworthiness: paragraphs the template tagged as
    ORCID, then the English header block, then the whole document. The last
    fallback matters because some templates put the ORCID line *after* the
    copyright byline, where the header-block scan cannot see it.
    """
    windows = []
    styled = paragraphs_with_role(paragraphs, "orcid")
    if styled:
        windows.append(styled)
    header_lines = _english_header_lines_before_copyright(
        paragraphs, literature_references
    )
    if header_lines:
        windows.append(header_lines)
    tail = _paragraphs_after_last_reference(paragraphs, literature_references)
    if tail:
        windows.append(tail)
    windows.append(list(paragraphs))

    for window in windows:
        orcids = _orcids_from_lines(window)
        if orcids:
            return orcids
    return []


def _styled_titles(paragraphs):
    """(ukrainian_title, english_title) from title-styled paragraphs.

    Assigned by script rather than by position, so it holds for both
    Ukrainian-first and English-first articles.
    """
    titled = [p for p in paragraphs_with_role(paragraphs, "title") if p.strip()]
    if not titled:
        return None, None
    ukrainian = next((p for p in titled if _has_cyrillic(p)), None)
    english = next((p for p in titled if not _has_cyrillic(p)), None)
    return ukrainian, english


MAX_HEADER_LINES = 15

EnglishHeader = namedtuple(
    "EnglishHeader", "title bylines affiliations abstract_index"
)


def _udc_index(paragraphs):
    """Index of the УДК line that opens the front matter, or None."""
    for index, paragraph in enumerate(paragraphs or []):
        if "УДК" in paragraph:
            return index
    return None


def _merge_title_at(paragraphs, index):
    """(title, index after it) for the title block starting at `index`.

    Titles are routinely split across paragraphs by a manual line break, so the
    continuation lines have to be absorbed before the header block is scanned.
    """
    if index is None or index >= len(paragraphs) or not paragraphs[index].strip():
        return "", index
    parts = [paragraphs[index].strip()]
    next_index = index + 1
    while next_index < len(paragraphs) and _looks_like_title_continuation(
        paragraphs[next_index]
    ):
        parts.append(paragraphs[next_index].strip())
        next_index += 1
    return " ".join(parts), next_index


def _leading_title(paragraphs):
    """Title of the front-matter header block (the one under the УДК line)."""
    udc_index = _udc_index(paragraphs)
    if udc_index is None:
        return ""
    return _merge_title_at(paragraphs, udc_index + 1)[0]


def _is_header_metadata_line(text):
    """True for the byline / affiliation / contact lines of an author block.

    Used to find where the header block ends, which is the first line that is
    none of these — i.e. the start of the abstract.
    """
    if not text or len(text) > 200:
        return False
    return bool(
        starts_with_copyright(text)
        or LICENSE_NOTICE_RE.search(text)
        or EMAIL_RE.search(text)
        or EMAIL_LABEL_RE.search(text)
        or ORCID_LINE_RE.search(text)
        or SUBMISSION_META_RE.search(text)
        or AFFILIATION_KEYWORDS_RE.search(text)
        or _looks_like_inline_author_line(text)
        or _looks_like_sole_author_byline(text)
        or _looks_like_full_name_byline(text)
    )


def _parse_english_header_after_literature(paragraphs, literature_references):
    """
    After the last literature reference: merge the multi-line English title, then
    split the header block into author byline(s) and affiliation lines.

    The block is scanned until the first non-metadata line (the abstract) rather
    than stopping at "(c)", because some templates place the affiliation and
    ORCID lines *after* the copyright byline.

    Returns an EnglishHeader: title, byline lines, affiliation lines, and the
    index at which the header ends (where the abstract begins).
    """
    if not literature_references:
        return EnglishHeader("English title not found.", [], [], None)

    last_index = _last_reference_index(paragraphs, literature_references)
    if last_index is None:
        return EnglishHeader("English title not found.", [], [], None)

    title_idx = last_index + 1
    if title_idx >= len(paragraphs):
        return EnglishHeader("English title not found.", [], [], None)

    title, j = _merge_title_at(paragraphs, title_idx)

    between = []
    limit = min(len(paragraphs), j + MAX_HEADER_LINES)
    while j < limit:
        text = paragraphs[j]
        if not _is_header_metadata_line(text):
            break
        between.append(text)
        j += 1

    bylines = []
    start = 0
    while start < len(between):
        line = between[start]
        if starts_with_copyright(line) or LICENSE_NOTICE_RE.search(line):
            break
        if is_byline_candidate(line):
            bylines.append(line)
            start += 1
            continue
        break

    # Templates without a © byline repeat a per-author block
    # ("Name / Institution / Department / ORCID / e-mail") once per author. The
    # name line directly above an institution line is the block's byline, so
    # every author gets credited rather than just the first.
    extra_bylines = {
        index
        for index in range(start, len(between) - 1)
        if is_byline_candidate(between[index])
        and AFFILIATION_KEYWORDS_RE.search(between[index + 1])
    }
    bylines.extend(between[index] for index in sorted(extra_bylines))

    affiliations = [
        line
        for index, line in enumerate(between)
        if index >= start
        and index not in extra_bylines
        and line.strip()
        and not starts_with_copyright(line)
        and not LICENSE_NOTICE_RE.search(line)
    ]
    return EnglishHeader(title, bylines, affiliations, j)


def is_byline_candidate(text):
    """True for a line that reads as an author byline in any of the templates."""
    return bool(
        _looks_like_inline_author_line(text)
        or _looks_like_sole_author_byline(text)
        or _looks_like_full_name_byline(text)
    )


def extract_affiliation_lines(paragraphs, literature_references):
    """Affiliation lines for the English author block."""
    styled = paragraphs_with_role(paragraphs, "affiliation")
    if styled:
        english = [str(p) for p in styled if not _has_cyrillic(p)]
        if english:
            return english
        return [str(p) for p in styled]
    return _parse_english_header_after_literature(
        paragraphs, literature_references
    ).affiliations


def extract_ukrainian_title(paragraphs):
    """Extracts the Ukrainian title (styled title, else the paragraph after 'УДК')."""
    styled_ukrainian, _ = _styled_titles(paragraphs)
    if styled_ukrainian:
        return str(styled_ukrainian)

    for i, paragraph in enumerate(paragraphs):
        if "УДК" in paragraph:
            candidate = paragraphs[i + 1] if i + 1 < len(paragraphs) else None
            if candidate and _has_cyrillic(candidate):
                return str(candidate)
            # English-first layout: the Ukrainian title sits in the trailing
            # Ukrainian block instead of directly under the УДК line.
            for later in paragraphs[i + 1 :]:
                if _has_cyrillic(later) and looks_like_uppercase_title(later):
                    return str(later)
            if candidate:
                return str(candidate)
            break
    return "Ukrainian title not found."


def extract_literature(paragraphs):
    """Extracts all literature references from the paragraphs."""
    styled = paragraphs_with_role(paragraphs, "references")
    if styled:
        return [str(p) for p in styled]

    heading_indices = [
        i
        for i, paragraph in enumerate(paragraphs)
        if REFERENCE_HEADING_RE.match(paragraph)
    ]
    # Reference lists sit at the end; a document may mention "References"
    # earlier, so prefer the last heading that actually yields entries.
    for index in reversed(heading_indices):
        references = _collect_reference_entries(paragraphs, index + 1)
        if references:
            return references
    return []


def _collect_reference_entries(paragraphs, start):
    """Reference entries following a heading, tolerating one wrapped line."""
    references = []
    misses = 0
    for paragraph in paragraphs[start:]:
        if references and _reference_list_has_ended(paragraph):
            break
        if REFERENCE_ENTRY_RE.search(paragraph):
            references.append(str(paragraph))
            misses = 0
            continue
        misses += 1
        if not references or misses >= 2:
            break
    return references


def _reference_list_has_ended(paragraph):
    """True at the start of the trailing author block that follows the references.

    Reference entries routinely contain years and URLs, so the copyright,
    ORCID, e-mail and submission-date lines of that block would otherwise be
    collected as references — which pushed the header block out of reach.
    """
    return bool(
        starts_with_copyright(paragraph)
        or ORCID_LINE_RE.search(paragraph)
        or EMAIL_LABEL_RE.search(paragraph)
        or SUBMISSION_META_RE.search(paragraph)
        or looks_like_uppercase_title(paragraph)
    )


def extract_english_title(paragraphs, literature_references):
    """Extracts the English title: styled, else whichever header block is Latin.

    Most articles are Ukrainian-first and put the English header after the
    references, but some are English-first and leave the Ukrainian block at the
    end. Picking by script instead of by position covers both.
    """
    _, styled_english = _styled_titles(paragraphs)
    if styled_english:
        return str(styled_english)

    trailing = _parse_english_header_after_literature(
        paragraphs, literature_references
    ).title
    if trailing and not _has_cyrillic(trailing):
        return trailing

    leading = _leading_title(paragraphs)
    if leading and not _has_cyrillic(leading):
        return leading
    return trailing or "English title not found."


def extract_authors(paragraphs, is_ukrainian=False, literature_references=None):
    """Extracts authors' names from the copyright byline.

    :param paragraphs: List of paragraphs from the DOCX file.
    :param is_ukrainian: Select the Ukrainian byline instead of the English one.
    :param literature_references: Enables the fallback to the plain author line
        under the title, for documents that carry no © byline at all.
    :return: Extracted authors' names.
    """
    indices = _copyright_byline_indices(paragraphs)
    matching = [
        paragraphs[i]
        for i in indices
        if _has_cyrillic(paragraphs[i]) == bool(is_ukrainian)
    ]
    if matching:
        # The English block trails the article, so the last byline is the one
        # belonging to it; the Ukrainian byline is the leading one.
        chosen = matching[0] if is_ukrainian else matching[-1]
        return _strip_copyright_decoration(chosen)

    fallback = _author_line_without_copyright(
        paragraphs, is_ukrainian, literature_references
    )
    if fallback:
        return _strip_copyright_decoration(fallback)
    return "Authors not found."


def _author_line_without_copyright(paragraphs, is_ukrainian, literature_references):
    """Author line for documents that have no © byline (template not followed)."""
    styled = [
        p for p in paragraphs_with_role(paragraphs, "authors") if p.strip()
    ]
    matching = [p for p in styled if _has_cyrillic(p) == bool(is_ukrainian)]
    if matching:
        return str(matching[0] if is_ukrainian else matching[-1])

    if is_ukrainian:
        return _bylines_under_ukrainian_title(paragraphs)

    return _join_bylines(
        _parse_english_header_after_literature(
            paragraphs, literature_references or []
        ).bylines
    )


def _join_bylines(bylines):
    """Merge byline lines into one comma-separated author list."""
    parts = [str(line).strip().rstrip(",").strip() for line in bylines or []]
    return ", ".join(part for part in parts if part) or None


def _bylines_under_ukrainian_title(paragraphs):
    """Author line(s) below the Ukrainian title, for documents with no © byline."""
    for i, paragraph in enumerate(paragraphs):
        if "УДК" not in paragraph:
            continue
        window = paragraphs[i + 1 : i + 1 + MAX_HEADER_LINES]
        bylines = []
        for index, candidate in enumerate(window):
            if not _has_cyrillic(candidate) or looks_like_uppercase_title(candidate):
                continue
            if not is_byline_candidate(candidate):
                continue
            # Either the line right under the title, or the name line heading a
            # per-author block.
            follower = window[index + 1] if index + 1 < len(window) else ""
            if bylines and not AFFILIATION_KEYWORDS_RE.search(follower):
                continue
            bylines.append(candidate)
        return _join_bylines(bylines)
    return None


def extract_abstract(paragraphs, literature_references=None, is_ukrainian=False):
    """Extracts the abstract of one language.

    :param literature_references: Enables the last-resort fallback that locates
        the abstract from the end of the trailing English header, for documents
        that carry neither an abstract style nor a © byline.
    :param is_ukrainian: Select the Ukrainian abstract instead of the English one.
    """
    styled = paragraphs_with_role(paragraphs, "abstract")
    if styled:
        wanted = [
            p
            for p in styled
            if _has_cyrillic(p) == bool(is_ukrainian) and not KEYWORDS_LINE_RE.match(p)
        ]
        joined = _join_abstract_lines(wanted)
        if joined:
            return joined
        # Only one language's abstract carries the style — the other is in a
        # plain paragraph, so fall through to locating it from the byline.

    start = _abstract_start(paragraphs, literature_references, is_ukrainian)
    if start is None:
        return "Abstract not found."

    collected = []
    for paragraph in paragraphs[start:]:
        # The licence notice also starts with "©", so it has to be skipped
        # before the "next byline" check below or the abstract ends at it.
        if (
            LICENSE_NOTICE_RE.search(paragraph)
            or SUBMISSION_META_RE.search(paragraph)
            or EMAIL_RE.search(paragraph)
            or ORCID_LINE_RE.search(paragraph)
        ):
            continue
        if (
            KEYWORDS_LINE_RE.match(paragraph)
            or starts_with_copyright(paragraph)
            or SECTION_HEADING_RE.match(paragraph)
        ):
            break
        if paragraph_role(paragraph) == "references":
            break
        collected.append(paragraph)
    return _join_abstract_lines(collected) or "Abstract not found."


def _abstract_start(paragraphs, literature_references, is_ukrainian=False):
    """Index where the abstract body of one language begins, or None.

    Tiers, most to least reliable: the paragraph after that language's © byline,
    the paragraph after a standalone "Abstract"/"Анотація" heading, the labelled
    "Abstract. ..." line itself, and — English only — the end of the trailing
    English header block.
    """
    wanted_script = bool(is_ukrainian)

    byline_indices = [
        i
        for i in _copyright_byline_indices(paragraphs)
        if _has_cyrillic(paragraphs[i]) == wanted_script
    ]
    if byline_indices:
        # The Ukrainian block opens the article and the English one closes it.
        return (byline_indices[0] if is_ukrainian else byline_indices[-1]) + 1

    def matching(pattern):
        return [
            i
            for i, paragraph in enumerate(paragraphs)
            if pattern.match(paragraph) and _has_cyrillic(paragraph) == wanted_script
        ]

    heading_indices = matching(ABSTRACT_HEADING_RE)
    if heading_indices:
        return heading_indices[-1] + 1

    labelled = matching(ABSTRACT_LABEL_RE)
    if labelled:
        return labelled[-1]

    if is_ukrainian:
        return _ukrainian_header_end(paragraphs)

    abstract_index = _parse_english_header_after_literature(
        paragraphs, literature_references or []
    ).abstract_index
    if abstract_index is not None and abstract_index < len(paragraphs):
        return abstract_index
    return None


def _ukrainian_header_end(paragraphs):
    """Index just past the opening УДК/title/author block, or None.

    Last resort for documents whose Ukrainian abstract has neither a heading nor
    a © byline above it — it simply follows the submission-date line.
    """
    for i, paragraph in enumerate(paragraphs):
        if "УДК" not in paragraph:
            continue
        j = i + 1
        limit = min(len(paragraphs), j + MAX_HEADER_LINES)
        while j < limit and (
            looks_like_uppercase_title(paragraphs[j])
            or _is_header_metadata_line(paragraphs[j])
        ):
            j += 1
        return j if j < len(paragraphs) else None
    return None


def extract_keywords(paragraphs, is_ukrainian=False):
    """Keyword list from the keywords line of one language."""
    label = UKRAINIAN_KEYWORDS_LABEL_RE if is_ukrainian else ENGLISH_KEYWORDS_LABEL_RE
    for paragraph in paragraphs or []:
        if label.match(paragraph):
            return split_keywords(label.sub("", str(paragraph), count=1))

    # Styled keyword paragraphs are not always labelled; fall back to script.
    for paragraph in paragraphs_with_role(paragraphs, "keywords"):
        if _has_cyrillic(paragraph) == bool(is_ukrainian):
            return split_keywords(KEYWORDS_LINE_RE.sub("", str(paragraph), count=1))
    return []


def split_keywords(text):
    items = [
        item.strip(" .;:,–—()[]")
        for item in re.split(r"[;,]", text or "")
        if item.strip()
    ]
    return [item for item in items if 0 < len(item) <= 80]


def _join_abstract_lines(lines):
    """Join abstract paragraphs, dropping a leading 'Abstract.' label."""
    cleaned = []
    for line in lines:
        text = ABSTRACT_LABEL_RE.sub("", str(line), count=1).strip()
        if text:
            cleaned.append(text)
    return "\n".join(cleaned).strip()
