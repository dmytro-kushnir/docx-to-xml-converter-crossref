"""Paragraph style -> semantic role mapping for the journal DOCX templates.

The article templates in circulation (``CSN:``, ``CSN SOT:``, ``ACPS:``, plus a
few Word built-ins) already tag most of the metadata we need with named
paragraph styles. Reading those roles is far more reliable than inferring
structure from text layout, so the extractors consult styles first and fall back
to text heuristics only for documents written without a template.

Example of why this matters: a copyright byline and the CC-BY licence notice are
both Latin-script paragraphs starting with "(c)", and only the style tells them
apart::

    CSN: Authors Italic   (c) Havrylov D.S., Musienko O.P. 2026   <- byline
    Normal (8pt)          (c) The Author(s). This is an open ...  <- licence
"""

import re

# Role -> pattern matched against the *local* part of a style name
# ("Literature Sources" for "CSN: Literature Sources"). Order matters: the first
# match wins, so narrower roles come before broader ones. In particular
# "Authors emails" and "Authors Italic" must be classified before "Authors".
_ROLE_PATTERNS = (
    ("email", r"^(authors?\s*e-?mails?|author_contact|e-?mails?)$"),
    ("orcid", r"^orcid$"),
    ("copyright", r"^(authors?\s*italic|copyright)$"),
    ("references", r"(literature\s*sources?|bibliography(_entry)?|^references?$)"),
    ("abstract", r"^(anotation|annotation|abstract)$"),
    ("keywords", r"^keywords?$"),
    ("title", r"^(article\s*name|article_title|english_title|title)$"),
    ("authors", r"^(authors?|authors_secondary)$"),
    ("affiliation", r"^(department|affiliation)$"),
    ("dates", r"^(editorial_dates|dates)$"),
    ("udc", r"^udc$"),
)

_COMPILED_ROLE_PATTERNS = tuple(
    (role, re.compile(pattern, re.IGNORECASE)) for role, pattern in _ROLE_PATTERNS
)


def style_family(style_name):
    """Template family a style belongs to ("CSN", "CSN SOT", "ACPS", or "")."""
    if not style_name or ":" not in style_name:
        return ""
    return style_name.rsplit(":", 1)[0].strip()


def _local_style_name(style_name):
    """Style name without its template prefix, normalised for matching."""
    if not style_name:
        return ""
    local = style_name.rsplit(":", 1)[-1]
    return re.sub(r"\s+", " ", local).strip().lower()


def style_role(style_name):
    """Semantic role for a style name, or "" when the style carries no meaning."""
    local = _local_style_name(style_name)
    if not local:
        return ""
    for role, pattern in _COMPILED_ROLE_PATTERNS:
        if pattern.search(local):
            return role
    return ""


def paragraph_role(paragraph):
    """Role of a paragraph; "" for plain strings that carry no style metadata."""
    return getattr(paragraph, "role", "") or ""


def paragraphs_with_role(paragraphs, *roles):
    """Paragraphs carrying any of the given roles, in document order."""
    wanted = set(roles)
    return [p for p in paragraphs or [] if paragraph_role(p) in wanted]


def has_role(paragraphs, *roles):
    """True when at least one paragraph carries one of the given roles."""
    return bool(paragraphs_with_role(paragraphs, *roles))


def template_families(paragraphs):
    """Distinct template families seen in a document (diagnostics/reporting)."""
    families = set()
    for paragraph in paragraphs or []:
        family = getattr(paragraph, "family", "")
        if family:
            families.add(family)
    return sorted(families)
