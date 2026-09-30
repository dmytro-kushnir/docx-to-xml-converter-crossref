"""Corpus audit for the anonymizer: does any identifying text survive?

Not a unit test — point it at a folder of real submissions and it reports what
leaked, per file. Reads every text node in the package (body, tables, text
boxes, headers/footers, footnotes/endnotes) plus the document properties,
because a reviewer opening the PDF sees all of them.

    python -m tests.anonymization_audit [input_folder]
"""

import re
import sys
import zipfile

from docx import Document

from docx_processing.extractors import split_copyright_authors
from docx_processing.parse import parse_docx, process_multiple_docs
from xml_generation.crossref.create_authors import parse_author_name

WORD_TEXT_PARTS = re.compile(
    r"^word/(document|header\d*|footer\d*|footnotes|endnotes|comments)\.xml$"
)
TEXT_NODE_RE = re.compile(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", re.DOTALL)
EMAIL_RE = re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}")
ORCID_RE = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b")
CORE_PROPS = ("author", "last_modified_by", "title", "subject", "comments", "category")


def package_text(docx_path):
    """All visible text in the package, concatenated per part."""
    chunks = []
    with zipfile.ZipFile(docx_path) as archive:
        for name in archive.namelist():
            if not WORD_TEXT_PARTS.match(name):
                continue
            xml = archive.read(name).decode("utf-8", errors="replace")
            for node in TEXT_NODE_RE.findall(xml):
                chunks.append(re.sub(r"<[^>]+>", "", node))
    return " ".join(chunks)


def identity_tokens(docx_path):
    """Surnames and given names to search for, from the original document."""
    from docx_processing.extractors import extract_authors, extract_literature

    paragraphs = parse_docx(docx_path)[0]
    literature = extract_literature(paragraphs)
    tokens = set()
    for is_ukrainian in (False, True):
        byline = extract_authors(paragraphs, is_ukrainian, literature)
        if not byline or byline.endswith("not found."):
            continue
        for author in split_copyright_authors(byline):
            parsed = parse_author_name(author)
            if not parsed:
                continue
            given, surname = parsed
            if len(surname) >= 4:
                tokens.add(surname.lower())
            # Full given names identify too; initials ("D. I.") do not.
            for part in given.replace(".", " ").split():
                if len(part) >= 4:
                    tokens.add(part.lower())
    return tokens


def leaks(anonymized_path, tokens):
    """Identifying strings still present in the anonymized package."""
    text = package_text(anonymized_path)
    lowered = text.lower()
    found = []
    for token in sorted(tokens):
        if re.search(rf"(?<![\w']){re.escape(token)}", lowered):
            found.append(token)
    emails = sorted(set(EMAIL_RE.findall(text)))
    orcids = sorted(set(ORCID_RE.findall(text)))

    props = []
    document = Document(anonymized_path)
    for prop in CORE_PROPS:
        value = getattr(document.core_properties, prop, None)
        if value and str(value).strip():
            props.append(f"{prop}={str(value).strip()[:40]!r}")
    return found, emails, orcids, props


def audit(input_folder):
    import os
    import tempfile

    from pdf_generation.anonymize_and_convert import anonymize_docx

    flagged = 0
    total = 0
    with tempfile.TemporaryDirectory() as temp_dir:
        for filename, _, _, _ in process_multiple_docs(input_folder):
            total += 1
            source = os.path.join(input_folder, filename)
            target = os.path.join(temp_dir, f"anon_{total}.docx")
            tokens = identity_tokens(source)
            try:
                anonymize_docx(source, target)
            except Exception as error:  # noqa: BLE001 - report, do not abort the sweep
                flagged += 1
                print(f"!! {filename}: anonymize_docx raised {error!r}")
                continue

            names, emails, orcids, props = leaks(target, tokens)
            problems = []
            if names:
                problems.append(f"names={names}")
            if emails:
                problems.append(f"emails={emails[:3]}")
            if orcids:
                problems.append(f"orcids={orcids[:3]}")
            if props:
                problems.append(f"properties=[{', '.join(props)}]")
            if not tokens:
                problems.append("NO-TOKENS (byline never extracted)")
            if problems:
                flagged += 1
                print(f"!! {filename}")
                for problem in problems:
                    print(f"     {problem}")

    print(f"\n{total} article(s), {flagged} still identifying")
    return flagged


if __name__ == "__main__":
    import yaml

    if len(sys.argv) > 1:
        folder = sys.argv[1]
    else:
        folder = yaml.safe_load(open("config.yml", encoding="utf-8"))["app"]["input_folder"]
    raise SystemExit(1 if audit(folder) else 0)
