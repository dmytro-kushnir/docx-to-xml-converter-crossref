"""The extracted form of one article, shared by validation and XML generation.

The XML generators consume a positional tuple. Keeping that tuple as the *only*
representation made it impossible to say which field a defect belonged to, so
extraction now produces an ``ArticleRecord`` and converts to the tuple at the
boundary via :meth:`ArticleRecord.to_tuple`.
"""

from dataclasses import dataclass, field


@dataclass
class ArticleRecord:
    """Metadata extracted from a single article DOCX."""

    filename: str
    english_title: str = ""
    ukrainian_title: str = ""
    authors: str = ""
    ukrainian_authors: str = ""
    start_page: int = 0
    end_page: int = 0
    literature: list = field(default_factory=list)
    abstract: str = ""
    ukrainian_abstract: str = ""
    english_keywords: list = field(default_factory=list)
    ukrainian_keywords: list = field(default_factory=list)
    affiliation_lines: list = field(default_factory=list)
    author_orcids: list = field(default_factory=list)
    template_families: list = field(default_factory=list)

    @property
    def pages(self):
        return (self.start_page, self.end_page)

    def language_payload(self):
        """Per-language text for ICI Copernicus, which deposits both languages.

        Kept out of :meth:`to_tuple` so the Crossref contract (and the page
        injection that rewrites those tuples) stays exactly as it was.
        """
        return {
            "en_abstract": self.abstract,
            "uk_abstract": self.ukrainian_abstract,
            "en_keywords": list(self.english_keywords or []),
            "uk_keywords": list(self.ukrainian_keywords or []),
        }

    def to_tuple(self):
        """Positional form expected by the Crossref / Copernicus generators."""
        return (
            self.english_title,
            self.ukrainian_title,
            self.authors,
            self.pages,
            self.literature,
            self.abstract,
            self.affiliation_lines,
            self.author_orcids,
        )
