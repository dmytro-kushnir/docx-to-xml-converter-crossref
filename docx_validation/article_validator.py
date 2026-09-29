"""Pre-flight validation of extracted article metadata.

Silent degradation was the real problem with the pipeline: an article whose
abstract never parsed still produced a perfectly well-formed
``<jats:abstract><jats:p>Abstract not available.</jats:p></jats:abstract>``, and
an unrecognised university silently inherited LPNU's ROR. Both reached Crossref
as facts. This module turns those into visible findings and lets ``main.py``
refuse to write the deposit.

Severity rules:

* ``ERROR``   — would deposit wrong or placeholder metadata. Blocks the write.
* ``WARNING`` — needs a human look but is often a genuine gap in the source
  (an author with no ORCID). Never blocks.

Page ranges are only ever warnings: they are provisional until the typeset PDF
exists, so they must not stop a run.
"""

from collections import namedtuple

from docx_processing.extractors import (
    CYRILLIC_RE,
    LICENSE_NOTICE_RE,
    affiliation_lines_for_crossref_organization,
    split_copyright_authors,
)
from xml_generation.crossref.institution_ror import resolve_institution

ERROR = "ERROR"
WARNING = "WARNING"

Finding = namedtuple("Finding", "severity code message")

# Text that means an extractor gave up, or that the author left the template
# boilerplate in place. Either way it must never reach Crossref.
_NOT_FOUND_MARKERS = ("not found.", "not available.")
_PLACEHOLDER_MARKERS = (
    "[author",
    "surname(s)",
    "author surname",
    "назва статті",
    "прізвище",
    "xxx",
)

MIN_ABSTRACT_CHARS = 100
MIN_REFERENCES = 3
# A research article never occupies fewer pages than this; a shorter range means
# the page count could not be read, not that the article is short.
MIN_PLAUSIBLE_PAGES = 4
MAX_PLAUSIBLE_PAGES = 40


def _is_missing(value):
    text = (value or "").strip()
    if not text:
        return True
    lowered = text.lower()
    return any(marker in lowered for marker in _NOT_FOUND_MARKERS)


def _is_placeholder(value):
    lowered = (value or "").lower()
    return any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


def validate_article(record, institutions_config=None, default_institution_id=None):
    """Findings for one ArticleRecord, most important first."""
    findings = []

    def error(code, message):
        findings.append(Finding(ERROR, code, message))

    def warn(code, message):
        findings.append(Finding(WARNING, code, message))

    if _is_missing(record.english_title):
        error("english-title", "English title not extracted")
    elif _is_placeholder(record.english_title):
        error("english-title", f"English title is template boilerplate: {record.english_title!r}")
    elif CYRILLIC_RE.search(record.english_title):
        # Deposited as <title>, so a Cyrillic value means the English-language
        # block has no English title of its own.
        error(
            "english-title",
            f"English title is in Cyrillic: {record.english_title!r}",
        )
    elif record.english_title.strip() == (record.ukrainian_title or "").strip():
        error("english-title", "English and Ukrainian titles are identical")

    if _is_missing(record.ukrainian_title):
        error("ukrainian-title", "Ukrainian title not extracted")
    elif not CYRILLIC_RE.search(record.ukrainian_title):
        error(
            "ukrainian-title",
            f"Ukrainian title has no Cyrillic characters: {record.ukrainian_title!r}",
        )

    findings.extend(_validate_authors(record))

    abstract = (record.abstract or "").strip()
    if _is_missing(abstract):
        error("abstract", "English abstract not extracted")
    elif len(abstract) < MIN_ABSTRACT_CHARS:
        warn(
            "abstract",
            f"English abstract is only {len(abstract)} characters — verify it is complete",
        )

    if not record.literature:
        error("references", "No literature references extracted")
    elif len(record.literature) < MIN_REFERENCES:
        warn(
            "references",
            f"Only {len(record.literature)} reference(s) extracted — verify the list is complete",
        )

    findings.extend(
        _validate_affiliation(record, institutions_config, default_institution_id)
    )
    findings.extend(_validate_orcids(record))
    findings.extend(_validate_pages(record))
    return findings


def _validate_authors(record):
    findings = []
    for label, code, value in (
        ("English", "authors", record.authors),
        ("Ukrainian", "ukrainian-authors", record.ukrainian_authors),
    ):
        if _is_missing(value):
            findings.append(Finding(ERROR, code, f"{label} author byline not extracted"))
            continue
        if _is_placeholder(value):
            findings.append(
                Finding(
                    ERROR,
                    code,
                    f"{label} author byline is template boilerplate: {value!r}",
                )
            )
            continue
        if LICENSE_NOTICE_RE.search(value):
            findings.append(
                Finding(
                    ERROR,
                    code,
                    f"{label} author byline looks like the licence notice: {value!r}",
                )
            )

    english_count = len(split_copyright_authors(record.authors))
    ukrainian_count = len(split_copyright_authors(record.ukrainian_authors))
    if english_count and ukrainian_count and english_count != ukrainian_count:
        findings.append(
            Finding(
                WARNING,
                "authors",
                f"{english_count} English author(s) but {ukrainian_count} Ukrainian — "
                "the two bylines disagree",
            )
        )
    return findings


def _validate_affiliation(record, institutions_config, default_institution_id):
    findings = []
    organization_lines = affiliation_lines_for_crossref_organization(
        record.affiliation_lines or []
    )
    if not organization_lines:
        findings.append(
            Finding(
                ERROR,
                "affiliation",
                "No institution line extracted — authors would be deposited with no affiliation",
            )
        )
        return findings

    primary = organization_lines[0]
    if not institutions_config:
        return findings

    resolved = resolve_institution(primary, institutions_config)
    if resolved:
        return findings

    fallback = resolve_institution(
        primary, institutions_config, default_institution_id=default_institution_id
    )
    if fallback:
        findings.append(
            Finding(
                ERROR,
                "institution-ror",
                f"{primary!r} is not in config.yml `institutions`, so it would be "
                f"deposited as {fallback['name']!r} — add its real ROR",
            )
        )
    else:
        findings.append(
            Finding(
                WARNING,
                "institution-ror",
                f"{primary!r} is not in config.yml `institutions` — no ROR will be "
                "deposited for these authors",
            )
        )
    return findings


def _validate_orcids(record):
    authors = split_copyright_authors(record.authors)
    if not authors:
        return []
    present = [orcid for orcid in (record.author_orcids or []) if orcid]
    if len(present) >= len(authors):
        return []
    return [
        Finding(
            WARNING,
            "orcid",
            f"{len(present)} ORCID(s) for {len(authors)} author(s) — the source "
            "document may be missing them",
        )
    ]


def _validate_pages(record):
    """Page findings are advisory: the range is provisional until the PDF exists."""
    start, end = record.start_page, record.end_page
    if not start or not end or end < start:
        return [Finding(WARNING, "pages", f"Implausible page range {start}-{end}")]

    span = end - start + 1
    if span < MIN_PLAUSIBLE_PAGES:
        return [
            Finding(
                WARNING,
                "pages",
                f"Page range {start}-{end} spans only {span} page(s) — the DOCX page "
                "count could not be read, so the DOI suffix is wrong",
            )
        ]
    if span > MAX_PLAUSIBLE_PAGES:
        return [
            Finding(
                WARNING,
                "pages",
                f"Page range {start}-{end} spans {span} pages — verify it",
            )
        ]
    return []


def validate_articles(records, institutions_config=None, default_institution_id=None):
    """Ordered mapping of filename -> findings for every record."""
    return {
        record.filename: validate_article(
            record, institutions_config, default_institution_id
        )
        for record in records
    }


def unmapped_institutions(records, institutions_config=None):
    """Primary affiliation lines with no ROR mapping, for a copy-paste config stub."""
    unmapped = []
    for record in records:
        organization_lines = affiliation_lines_for_crossref_organization(
            record.affiliation_lines or []
        )
        if not organization_lines:
            continue
        primary = organization_lines[0]
        if resolve_institution(primary, institutions_config or {}):
            continue
        if primary not in unmapped:
            unmapped.append(primary)
    return unmapped


def count_by_severity(results, severity):
    return sum(
        1
        for findings in results.values()
        for finding in findings
        if finding.severity == severity
    )


def has_errors(results):
    return count_by_severity(results, ERROR) > 0


def format_report(results, institutions_config=None):
    """Human-readable report; empty-clean articles are summarised, not listed."""
    lines = ["", "=" * 72, "VALIDATION REPORT", "=" * 72]

    clean = []
    for filename, findings in results.items():
        if not findings:
            clean.append(filename)
            continue
        lines.append("")
        lines.append(f"{filename}")
        for finding in findings:
            lines.append(f"  [{finding.severity:<7}] {finding.code}: {finding.message}")

    errors = count_by_severity(results, ERROR)
    warnings = count_by_severity(results, WARNING)
    lines.append("")
    lines.append("-" * 72)
    lines.append(
        f"{len(results)} article(s): {len(clean)} clean, "
        f"{errors} error(s), {warnings} warning(s)"
    )
    if clean:
        lines.append(f"Clean: {', '.join(clean)}")
    lines.append("=" * 72)
    return "\n".join(lines)


def format_institution_stub(institution_lines):
    """YAML skeleton for affiliations that still need a ROR, ready to paste."""
    if not institution_lines:
        return ""
    lines = [
        "",
        "Add the missing ROR identifiers to config.yml `institutions`",
        "(look each one up at https://ror.org/search):",
        "",
    ]
    for index, name in enumerate(institution_lines, start=1):
        lines.append(f"  institution_{index}:")
        lines.append(f'    name: "{name}"')
        lines.append('    ror: ""  # <- fill in')
    return "\n".join(lines)
