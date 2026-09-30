"""Produce a double-blind reviewer copy of each submission, as PDF.

Anything identifying has to go, and it hides in more places than the author
block: self-citations in the reference list, running headers, table cells, text
boxes, footnotes, and the DOCX document properties that LibreOffice copies
straight into the PDF metadata.

Two passes, because the two kinds of leak need opposite treatment:

* **structural** — the author block itself (byline, affiliation, e-mail, ORCID,
  submission dates) is blanked outright. It is located by paragraph *style role*
  first, exactly like the metadata extractors do, and by text heuristics only
  inside the header regions. Scoping matters: "centre" and "authors" are
  ordinary words, so an unscoped keyword rule deletes body sentences such as
  "The authors of [7] developed ..." and any paragraph mentioning a data centre.
* **lexical** — every remaining mention of an author's name anywhere in the
  package is replaced with a placeholder, leaving the surrounding text intact. A
  self-citation stays readable as a citation without naming the author.

Both passes work on ``w:t`` nodes rather than ``Document.paragraphs``, because
that property sees neither table cells nor text boxes.
"""

import argparse
import io
import os
import re
import tempfile
import zipfile

from docx import Document
from docx.oxml.ns import qn
from docx.text.paragraph import Paragraph

from docx_processing.extractors import (
    ABSTRACT_HEADING_RE,
    ABSTRACT_LABEL_RE,
    AFFILIATION_KEYWORDS_RE,
    COPYRIGHT_PREFIX_RE,
    EMAIL_LABEL_RE,
    EMAIL_RE,
    KEYWORDS_LINE_RE,
    LICENSE_NOTICE_RE,
    ORCID_LINE_RE,
    SUBMISSION_META_RE,
    extract_literature,
    looks_like_uppercase_title,
    split_copyright_authors,
    starts_with_copyright,
)
from docx_processing.parse import StyledText
from pdf_generation.generate_pdf import _check_libreoffice_installed, _convert_docx_to_pdf
from xml_generation.crossref.create_authors import parse_author_name

REDACTED = "[anonymized]"

# Shorter fragments match too much ordinary text to be worth redacting, and
# initials ("D.", "Yu.") carry little identity on their own.
MIN_TERM_LENGTH = 4
# Ukrainian surnames inflect ("Совин" -> "Совина", "Совинові"), so a term is
# allowed to carry a short case ending.
INFLECTION_SUFFIX = 3

# How far the author block can reach from the start of the document, and from
# the start of the second-language block that follows the references.
HEADER_SCAN_LINES = 30
# Author-block lines cluster around the © byline in every template seen so far.
COPYRIGHT_NEIGHBOURHOOD = 3
# An affiliation is a short line; a sentence that happens to mention a
# university is not.
MAX_AFFILIATION_LENGTH = 160
# Content roles: never blanked wholesale, only redacted term by term.
PROTECTED_ROLES = ("title", "abstract", "keywords", "references", "udc")

# Document properties that name a person or repeat the submission's own text.
IDENTIFYING_PROPERTIES = (
    "author",
    "last_modified_by",
    "category",
    "comments",
    "keywords",
    "subject",
    "identifier",
    # Word seeds the title from the first line typed, which in these
    # submissions is as often the author's name as the article's.
    "title",
)
# docProps/app.xml equivalents, which python-docx does not expose.
APP_PROPERTY_TAGS = ("Company", "Manager")
# Package parts holding text that Document.paragraphs cannot reach.
EXTRA_TEXT_PARTS = re.compile(r"^word/(footnotes|endnotes|comments)\.xml$")


def _slugify_for_filename(text, max_len=40):
    if not text:
        return "untitled"
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:max_len].rstrip("-") or "untitled"


# --------------------------------------------------------------------------
# Identity terms
# --------------------------------------------------------------------------

MAX_BYLINE_LENGTH = 200
MAX_AUTHORS_PER_LINE = 8
# A name token: an initial ("D.", "Ю.В.") or a capitalised word.
INITIAL_TOKEN_RE = re.compile(r"^(?:[^\W\d_]\.){1,4}$")
# "D. S." / "Ю.В." as it appears next to a surname. Ends on the final
# dot, so substituting it does not swallow the space that follows.
INITIALS_FRAGMENT = r"[^\W\d_]\.(?:[ \t ]*[^\W\d_]\.){0,3}"
NAME_TOKEN_RE = re.compile(r"^[^\W\d_](?:[^\W\d_]|['’\-])*$")
AUTHOR_SEPARATOR_RE = re.compile(r"\s*(?:,|;|\band\b|\bта\b|&)\s*", re.IGNORECASE)


def _name_words(text):
    """Whole-word name components, dropping initials and short fragments."""
    return {
        word.lower()
        for word in re.split(r"[^\w'’\-]+", text or "")
        if len(word) >= MIN_TERM_LENGTH and not re.search(r"\d|_", word)
    }


def _byline_candidate_text(text):
    """A byline line stripped of ©, trailing year and affiliation markers."""
    candidate = (text or "").strip().strip("*_").strip()
    candidate = COPYRIGHT_PREFIX_RE.sub("", candidate).strip()
    candidate = re.sub(r"[\s,]*\b\d{4}\b\s*[*_]*$", "", candidate).strip(" ,*_")
    # Affiliation footnote markers, which attach either to the surname
    # ("Складанний П.М.1") or to the initials after it ("Skladannyi P.M.1").
    return re.sub(r"(?<=[^\W\d_]|\.)\d+(?=[\s,]|$)", "", candidate).strip()


def _is_name_list(text, allow_uppercase=False):
    """True only for a line made up entirely of personal names.

    Deliberately stricter than ``is_byline_candidate``: that predicate accepts
    any line containing a comma, which is right where it is used (on lines
    already known to sit in an author block) but would mine every abstract
    paragraph for "names" here. Prose fails because it contains lower-case
    words; an ALL-CAPS title fails unless the line is structurally trusted,
    since titles and shouted bylines are otherwise indistinguishable.
    """
    if not text or len(text) > MAX_BYLINE_LENGTH:
        return False
    parts = [part for part in AUTHOR_SEPARATOR_RE.split(text) if part.strip()]
    if not 1 <= len(parts) <= MAX_AUTHORS_PER_LINE:
        return False

    has_initial = False
    has_surname = False
    for part in parts:
        tokens = part.split()
        if not 2 <= len(tokens) <= 4:
            return False
        for token in tokens:
            if INITIAL_TOKEN_RE.match(token):
                has_initial = True
                continue
            token = token.rstrip(".")
            if not NAME_TOKEN_RE.match(token) or not token[0].isupper():
                return False
            if len(token) >= MIN_TERM_LENGTH:
                has_surname = True
                if not allow_uppercase and token.isupper():
                    return False
    return has_surname or has_initial


def _byline_terms(text, trusted=False):
    """Name components of a line, but only if it really reads as a byline.

    Templates apply the author styles loosely — affiliation, e-mail and date
    lines all turn up styled ``CSN: Authors`` — so a line is only mined for
    names once everything else it could be has been ruled out. Harvesting the
    licence notice, in particular, would add "author", "creative" and "license"
    as redaction terms and gut the whole document.
    """
    if not text or LICENSE_NOTICE_RE.search(text):
        return set()
    if (
        EMAIL_RE.search(text)
        or EMAIL_LABEL_RE.search(text)
        or ORCID_LINE_RE.search(text)
        or SUBMISSION_META_RE.search(text)
        or AFFILIATION_KEYWORDS_RE.search(text)
    ):
        return set()

    candidate = _byline_candidate_text(text)
    if not _is_name_list(candidate, allow_uppercase=trusted):
        return set()

    terms = set()
    for author in split_copyright_authors(candidate):
        parsed = parse_author_name(author)
        if parsed:
            given, surname = parsed
            terms |= _name_words(surname) | _name_words(given)
        else:
            terms |= _name_words(author)
    return terms


def identity_terms(styled, header_indices):
    """Lower-cased surnames and full given names of the article's authors.

    Collected from every line that reads as a byline, in both languages, so the
    Ukrainian and the transliterated spelling of each name are both covered. The
    author-styled and © lines are trusted anywhere; anything else is only mined
    inside the header regions, where a bare list of names cannot be prose.
    """
    terms = set()
    for index, paragraph in enumerate(styled):
        if not paragraph:
            continue
        role = paragraph.role
        trusted = role in ("copyright", "authors") or starts_with_copyright(paragraph)
        if trusted:
            terms |= _byline_terms(paragraph, trusted=True)
        elif index in header_indices and role not in PROTECTED_ROLES:
            terms |= _byline_terms(paragraph)
    return {term for term in terms if len(term) >= MIN_TERM_LENGTH}


def _match_stem(term):
    """Stem to match on, so inflected forms of a surname are still caught.

    Ukrainian surnames change their final vowel as well as taking an ending
    ("Хохлачова" -> "Хохлачової"), so a term ending in a vowel matches on its
    consonant stem. Only when the stem stays long enough to be distinctive.
    """
    if len(term) >= 6 and term[-1] in "аяоеиіуюї":
        return term[:-1]
    return term


def identity_pattern(terms):
    """Whole-word pattern matching any identity term, or None.

    Two details matter. A match has to cover a complete word, or the allowance
    for a case ending stops mid-word and "МОДЕЛЬ" becomes "[anonymized]ЕЛЬ".
    And initials next to the name are swallowed with it, so a self-citation
    reads "[anonymized] (2026)" rather than "[anonymized], Д. С. (2026)".
    """
    if not terms:
        return None
    stems = {_match_stem(term) for term in terms}
    alternatives = "|".join(
        re.escape(stem) for stem in sorted(stems, key=len, reverse=True)
    )
    return re.compile(
        # (?<!-) keeps a hyphenated co-author's initial ("Le Boudec, J.-Y.")
        # from being pulled into the name that follows it.
        rf"(?<![^\W\d_])(?:(?<!-){INITIALS_FRAGMENT},?[ \t ]*)?"
        rf"(?:{alternatives})[^\W\d_]{{0,{INFLECTION_SUFFIX}}}(?![^\W\d_])"
        rf"(?:[ \t ]*,?[ \t ]*{INITIALS_FRAGMENT})?",
        re.IGNORECASE,
    )


# --------------------------------------------------------------------------
# Paragraph-level editing, at the XML text-node level
# --------------------------------------------------------------------------

def _text_nodes(element):
    return list(element.iter(qn("w:t")))


def _element_text(element):
    return "".join(node.text or "" for node in _text_nodes(element))


def _blank_element(element):
    """Drop the text but keep the paragraph, so spacing and layout survive."""
    changed = False
    for node in _text_nodes(element):
        if node.text:
            node.text = ""
            changed = True
    return changed


def _set_element_text(element, replacement):
    """Put `replacement` in the first text node and clear the rest."""
    nodes = _text_nodes(element)
    if not nodes:
        return False
    nodes[0].text = replacement
    for node in nodes[1:]:
        node.text = ""
    return True


def _redact_element(element, pattern):
    """Replace identity terms in place, keeping the rest of the text.

    Word splits a paragraph into runs wherever formatting or a spell-check mark
    changes, so a name can straddle two text nodes. A per-node substitution
    would then redact one half and leave the other ("[anonymized], Д. С."), so a
    straddling match forces the paragraph to be rewritten as a single node —
    which costs its inline formatting, hence only when it is actually needed.
    """
    if pattern is None:
        return False
    nodes = [node for node in _text_nodes(element) if node.text]
    if not nodes:
        return False

    spans = []
    offset = 0
    for node in nodes:
        spans.append((offset, offset + len(node.text), node))
        offset += len(node.text)

    text = "".join(node.text for node in nodes)
    matches = list(pattern.finditer(text))
    if not matches:
        return False

    straddles = any(
        not any(start <= match.start() and match.end() <= end for start, end, _ in spans)
        for match in matches
    )
    if straddles:
        _set_element_text(element, pattern.sub(REDACTED, text))
    else:
        for _, _, node in spans:
            node.text = pattern.sub(REDACTED, node.text)
    return True


def _anonymous_copyright(text):
    year = re.search(r"(\d{4})", text)
    return f"© Anonymous {year.group(1)}" if year else "© Anonymous"


def _is_contact_line(text):
    """Contact / identifier lines, safe to blank anywhere in the document."""
    return bool(
        EMAIL_RE.search(text)
        or EMAIL_LABEL_RE.search(text)
        or ORCID_LINE_RE.search(text)
        or SUBMISSION_META_RE.search(text)
    )


def _is_author_block_line(text, role, in_header, pattern):
    """True when the whole paragraph belongs to an author block."""
    if not text:
        return False
    if role in ("email", "orcid", "dates") or _is_contact_line(text):
        return True
    # The title, abstract, keywords and references say nothing identifying by
    # themselves; any name inside them is handled by the lexical pass. Their own
    # label outranks the style, because templates label a keywords line
    # "CSN: Authors Italic" — the style means "italic", not "byline".
    if role in PROTECTED_ROLES or KEYWORDS_LINE_RE.match(text) or ABSTRACT_LABEL_RE.match(text):
        return False
    candidate = _byline_candidate_text(text)
    if (
        looks_like_uppercase_title(text)
        and not starts_with_copyright(text)
        and not _is_name_list(candidate, allow_uppercase=True)
    ):
        # Some submissions style their title "CSN: Authors" outright. A byline
        # typed in capitals still reads as a list of names; a title does not.
        return False
    if role in ("authors", "copyright") and not LICENSE_NOTICE_RE.search(text):
        return True
    if not in_header:
        return False
    # Inside the header only: an affiliation line, or a short line that is
    # nothing but names. Unscoped, either rule would delete ordinary prose —
    # "the authors of [7]" and any mention of a data centre.
    if role == "affiliation":
        return True
    if len(text) <= MAX_AFFILIATION_LENGTH and AFFILIATION_KEYWORDS_RE.search(text):
        return True
    if _is_name_list(_byline_candidate_text(text), allow_uppercase=False):
        return True
    return bool(pattern and len(text) <= MAX_BYLINE_LENGTH and pattern.search(text))


def _styled_view(paragraph_elements, document):
    """StyledText per paragraph element, so style roles are available by index."""
    styled = []
    for element in paragraph_elements:
        paragraph = Paragraph(element, document)
        try:
            style_name = paragraph.style.name or ""
        except (AttributeError, KeyError):
            style_name = ""
        styled.append(StyledText(_element_text(element).strip(), style=style_name))
    return styled


def _is_abstract_boundary(paragraph):
    """True where the front matter ends and the article's own text begins."""
    return bool(
        paragraph.role in ("abstract", "keywords")
        or ABSTRACT_LABEL_RE.match(paragraph)
        or ABSTRACT_HEADING_RE.match(paragraph)
        or KEYWORDS_LINE_RE.match(paragraph)
    )


def _header_indices(styled, literature):
    """Paragraph indices that may legitimately contain an author block.

    An author block runs from the top of a language block down to its abstract,
    and the document has two of them: the article opens with one and the
    second-language summary after the references starts another. Bounding the
    region this way keeps body headings out of it — "Literature Review" is two
    capitalised words and otherwise indistinguishable from a two-word byline.
    """
    non_empty = [index for index, text in enumerate(styled) if text]
    starts = [0]
    if literature:
        last = max(
            (index for index, text in enumerate(styled) if str(text) == str(literature[-1])),
            default=None,
        )
        if last is not None:
            starts.append(last + 1)

    header = set()
    for start in starts:
        window = [index for index in non_empty if index >= start][:HEADER_SCAN_LINES]
        for index in window:
            if _is_abstract_boundary(styled[index]):
                break
            header.add(index)

    # The © byline, and the contact lines clustered around it, can sit just
    # below the abstract in some templates. The CC-BY notice is also a © line
    # but sits in the middle of the body, so expanding around it would put
    # ordinary prose inside the author block.
    for index, text in enumerate(styled):
        if starts_with_copyright(text) and _is_name_list(
            _byline_candidate_text(text), allow_uppercase=True
        ):
            header.update(
                range(index - COPYRIGHT_NEIGHBOURHOOD, index + COPYRIGHT_NEIGHBOURHOOD + 1)
            )
    return header


# --------------------------------------------------------------------------
# Document-level anonymization
# --------------------------------------------------------------------------

def _scrub_properties(document):
    """Clear the properties LibreOffice copies into the PDF metadata."""
    properties = document.core_properties
    for name in IDENTIFYING_PROPERTIES:
        if getattr(properties, name, None):
            setattr(properties, name, "")


def _scrub_package_parts(target, pattern):
    """Redact the parts python-docx cannot reach: footnotes, endnotes, app.xml.

    `target` is whatever the caller passed as the destination — a path or an
    open binary stream — and is rewritten in place.
    """
    if hasattr(target, "seek"):
        target.seek(0)
        original = target.read()
    else:
        with open(target, "rb") as handle:
            original = handle.read()

    rewritten = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(original)) as archive:
        entries = [(item, archive.read(item.filename)) for item in archive.infolist()]
    with zipfile.ZipFile(rewritten, "w", zipfile.ZIP_DEFLATED) as archive:
        for item, payload in entries:
            data = payload
            if EXTRA_TEXT_PARTS.match(item.filename) and pattern:
                text = payload.decode("utf-8", errors="replace")
                data = _redact_xml_text(text, pattern).encode("utf-8")
            elif item.filename == "docProps/app.xml":
                text = payload.decode("utf-8", errors="replace")
                for tag in APP_PROPERTY_TAGS:
                    text = re.sub(
                        rf"<{tag}>.*?</{tag}>", f"<{tag}></{tag}>", text, flags=re.DOTALL
                    )
                data = text.encode("utf-8")
            archive.writestr(item, data)

    if hasattr(target, "seek"):
        target.seek(0)
        target.truncate()
        target.write(rewritten.getvalue())
    else:
        with open(target, "wb") as handle:
            handle.write(rewritten.getvalue())


def _redact_xml_text(xml, pattern):
    def replace(match):
        return f"{match.group(1)}{pattern.sub(REDACTED, match.group(2))}{match.group(3)}"

    return re.sub(r"(<w:t(?:\s[^>]*)?>)(.*?)(</w:t>)", replace, xml, flags=re.DOTALL)


def anonymize_docx(docx_path, output_docx_path):
    """Write an anonymized copy of `docx_path` to `output_docx_path`."""
    document = Document(docx_path)

    body_paragraphs = list(document.element.body.iter(qn("w:p")))
    styled = _styled_view(body_paragraphs, document)
    literature = extract_literature([text for text in styled if text])
    header = _header_indices(styled, literature)
    terms = identity_terms(styled, header)
    pattern = identity_pattern(terms)

    for index, element in enumerate(body_paragraphs):
        text = str(styled[index])
        if not text:
            continue
        if starts_with_copyright(text) and not LICENSE_NOTICE_RE.search(text):
            _set_element_text(element, _anonymous_copyright(text))
            continue
        if _is_author_block_line(text, styled[index].role, index in header, pattern):
            _blank_element(element)
            continue
        _redact_element(element, pattern)

    # Running heads and feet routinely repeat the author names.
    for section in document.sections:
        for part in (
            section.header,
            section.first_page_header,
            section.even_page_header,
            section.footer,
            section.first_page_footer,
            section.even_page_footer,
        ):
            for element in part._element.iter(qn("w:p")):
                text = _element_text(element).strip()
                if not text:
                    continue
                if (
                    _is_contact_line(text)
                    or _is_name_list(_byline_candidate_text(text), allow_uppercase=True)
                    or (pattern and pattern.search(text))
                ):
                    _blank_element(element)
                else:
                    _redact_element(element, pattern)

    _scrub_properties(document)
    document.save(output_docx_path)
    _scrub_package_parts(output_docx_path, pattern)
    return terms


def process_and_convert_folder(input_folder, output_folder):
    from docx_processing.extractors import extract_english_title
    from docx_processing.parse import process_multiple_docs

    _check_libreoffice_installed()
    os.makedirs(output_folder, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        for index, (filename, paragraphs, _, _) in enumerate(
            process_multiple_docs(input_folder), start=1
        ):
            input_path = os.path.join(input_folder, filename)
            literature = extract_literature(paragraphs)
            title = extract_english_title(paragraphs, literature)
            stem = f"anonymous_{index:03d}_{_slugify_for_filename(title)}"

            # Named after the anonymous stem, never after the submission: the
            # source filename is usually the author's surname, and LibreOffice
            # derives the PDF name (and the PDF's own title) from it.
            temp_docx_path = os.path.join(temp_dir, f"{stem}.docx")
            anonymize_docx(input_path, temp_docx_path)

            expected_pdf = os.path.join(output_folder, f"{stem}.pdf")
            _convert_docx_to_pdf(temp_docx_path, expected_pdf)
            if not os.path.exists(expected_pdf):
                print(f"Warning: no PDF produced for {filename}")


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Anonymize DOCX author lines and convert to PDF.",
    )
    parser.add_argument(
        "input_folder",
        nargs="?",
        help="Folder containing DOCX files to anonymize and convert.",
    )
    parser.add_argument(
        "--output-name",
        default="anonymized_pdfs",
        help="Folder name under ./output for generated PDFs.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_folder = args.input_folder or os.path.join(script_dir, "input")
    output_folder = os.path.join(script_dir, "output", args.output_name)
    process_and_convert_folder(input_folder, output_folder)
