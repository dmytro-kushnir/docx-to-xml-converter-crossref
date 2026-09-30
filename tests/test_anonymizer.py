"""Regression tests for the double-blind anonymizer.

Each class is a way a name used to survive into the reviewer's PDF, or a way
the redaction used to destroy text it should have left alone:

* a byline typed in capitals, or carrying affiliation superscripts, or wrapped
  in emphasis markers, so the © line was never recognised;
* a self-citation in the reference list, which the old length guard skipped;
* text in a table cell, a text box, or a running header, none of which
  ``Document.paragraphs`` reaches;
* the document properties, which LibreOffice copies into the PDF metadata;
* and in the other direction, ordinary prose about "the authors of [7]" or a
  data centre, which an unscoped keyword rule deleted outright.
"""

import io
import re
import unittest
import zipfile

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import parse_xml
from docx.oxml.ns import nsmap, qn

from pdf_generation.anonymize_and_convert import (
    REDACTED,
    anonymize_docx,
    identity_pattern,
    identity_terms,
)

LICENCE = (
    "© The Author(s). This is an open access article distributed under the terms "
    "of the Creative Commons Attribution License."
)
ABSTRACT_EN = (
    "Abstract. The paper presents a scheduling method for edge deployments and "
    "evaluates it on recorded traces, showing it outperforms the baseline."
)


class DocumentBuilder:
    """Assembles an in-memory DOCX, registering template styles on demand."""

    def __init__(self):
        self.document = Document()
        self._styles = {}

    def _style(self, name):
        if name not in self._styles:
            self._styles[name] = self.document.styles.add_style(
                name, WD_STYLE_TYPE.PARAGRAPH
            )
        return self._styles[name]

    def add(self, text, style=None):
        paragraph = self.document.add_paragraph(text)
        if style:
            paragraph.style = self._style(style)
        return paragraph

    def add_table_cell(self, text):
        table = self.document.add_table(rows=1, cols=1)
        table.cell(0, 0).text = text

    def add_text_box(self, text):
        """A paragraph inside a text box, reachable only through w:txbxContent."""
        paragraph = self.document.add_paragraph()
        xml = (
            '<w:r {ns}><w:pict><v:shape xmlns:v="urn:schemas-microsoft-com:vml">'
            "<v:textbox><w:txbxContent><w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
            "</w:txbxContent></v:textbox></v:shape></w:pict></w:r>"
        ).format(
            ns=" ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in nsmap.items()),
            text=text,
        )
        paragraph._p.append(parse_xml(xml))

    def anonymized(self):
        source = io.BytesIO()
        self.document.save(source)
        source.seek(0)
        result = io.BytesIO()
        anonymize_docx(source, result)
        result.seek(0)
        return result


TEXT_NODE_RE = re.compile(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", re.DOTALL)


def full_text(stream):
    """Every text node in the package, so tables and text boxes count too."""
    stream.seek(0)
    chunks = []
    with zipfile.ZipFile(stream) as archive:
        for name in archive.namelist():
            if name.startswith("word/") and name.endswith(".xml"):
                xml = archive.read(name).decode("utf-8", errors="replace")
                chunks.extend(TEXT_NODE_RE.findall(xml))
    return "\n".join(chunks)


def paragraph_texts(stream):
    stream.seek(0)
    document = Document(stream)
    return [
        "".join(node.text or "" for node in element.iter(qn("w:t"))).strip()
        for element in document.element.body.iter(qn("w:p"))
    ]


def front_matter(builder, byline, *, styled_byline=True):
    """A minimal article header ending in `byline` as the © line."""
    builder.add("COMPUTER SYSTEMS AND NETWORKS")
    builder.add("УДК 004.7")
    builder.add("SCHEDULING METHOD FOR EDGE DEPLOYMENTS", "CSN: Article name")
    builder.add(byline, "CSN: Authors Italic" if styled_byline else None)
    builder.add("Lviv Polytechnic National University", "CSN: Affiliation")
    builder.add("E-mail: author.one@lpnu.ua", "CSN: Authors emails")
    builder.add(ABSTRACT_EN, "CSN: Anotation")
    builder.add(LICENCE)


class BylinePatternTests(unittest.TestCase):
    """Byline shapes whose names used to survive the ©-line detection."""

    def assert_byline_removed(self, byline, surname):
        builder = DocumentBuilder()
        front_matter(builder, byline)
        builder.add(f"A later paragraph citing {surname} and nothing else.")
        text = full_text(builder.anonymized())
        self.assertNotIn(surname, text)
        self.assertIn(REDACTED, text)

    def test_uppercase_byline(self):
        self.assert_byline_removed("© ГАВРИЛОВ Д.С., МУСІЄНКО О.П., 2026", "ГАВРИЛОВ")

    def test_byline_with_affiliation_superscripts(self):
        self.assert_byline_removed(
            "© Skladannyi P.M.1, Kostiuk Y.V.1, Hnatchenko D.D.2 2026", "Skladannyi"
        )

    def test_byline_wrapped_in_emphasis_markers(self):
        self.assert_byline_removed("*© Hrytsko T.L., Hlukhov V.S. 2026*", "Hrytsko")

    def test_hyphenated_surname(self):
        self.assert_byline_removed(
            "© D. I. Prokopovych-Tkachenko, 2026", "Prokopovych-Tkachenko"
        )

    def test_full_names_without_initials(self):
        self.assert_byline_removed("© Yuliia Khokhlachova, 2026", "Khokhlachova")

    def test_copyright_line_is_replaced_not_dropped(self):
        builder = DocumentBuilder()
        front_matter(builder, "© Sovyn Y. R., Nakonechnyi Yu. M. 2026")
        self.assertIn("© Anonymous 2026", paragraph_texts(builder.anonymized()))

    def test_licence_notice_survives(self):
        builder = DocumentBuilder()
        front_matter(builder, "© Sovyn Y. R. 2026")
        self.assertIn(LICENCE, paragraph_texts(builder.anonymized()))


class SelfCitationTests(unittest.TestCase):
    """A name in the reference list or body prose, which must be redacted in place."""

    def anonymize_with_body(self, *body):
        builder = DocumentBuilder()
        front_matter(builder, "© Sovyn Y. R., Nakonechnyi Yu. M. 2026")
        for line in body:
            builder.add(line)
        builder.add("References", "CSN: Literature Sources")
        return builder

    def test_reference_entry_is_redacted_but_kept(self):
        reference = (
            "12. Sovyn, Y. R., & Opirskyy, I. R. (2023). Minimisation of bitsliced "
            "representation of 4x4 S-boxes. Computer Systems and Networks, 5(1), 1-12."
        )
        builder = self.anonymize_with_body(reference)
        texts = paragraph_texts(builder.anonymized())
        entry = next(text for text in texts if "bitsliced" in text)
        self.assertNotIn("Sovyn", entry)
        self.assertIn(REDACTED, entry)
        # Still readable as a citation: the co-author, year and venue remain.
        self.assertIn("Opirskyy", entry)
        self.assertIn("(2023)", entry)
        self.assertIn("Computer Systems and Networks", entry)

    def test_initials_next_to_the_name_go_with_it(self):
        builder = self.anonymize_with_body("14. Sovyn, Y. R. (2024). A method. Journal.")
        entry = next(
            text for text in paragraph_texts(builder.anonymized()) if "A method" in text
        )
        self.assertNotIn("Y. R.", entry)
        self.assertIn(f"{REDACTED} (2024)", entry)

    def test_inflected_ukrainian_surname_is_matched(self):
        builder = DocumentBuilder()
        front_matter(builder, "© Совин Я. Р., 2026")
        builder.add("Підхід, запропонований Совином, розвинуто у роботі [4].")
        builder.add("Результати Хохлачової не порівнювалися з нашими.")
        text = full_text(builder.anonymized())
        self.assertNotIn("Совин", text)
        # A name that is not an author of this article stays.
        self.assertIn("Хохлачової", text)


class OverClearingTests(unittest.TestCase):
    """Text that an unscoped keyword rule used to delete."""

    def setUp(self):
        self.builder = DocumentBuilder()
        front_matter(self.builder, "© Sovyn Y. R. 2026")

    def assert_survives(self, line):
        self.builder.add(line)
        self.assertIn(line, paragraph_texts(self.builder.anonymized()))

    def test_prose_mentioning_authors_survives(self):
        self.assert_survives(
            "The authors of [7] developed an integrated smart metering system "
            "and reported a 12% reduction in peak load."
        )

    def test_prose_mentioning_a_centre_survives(self):
        self.assert_survives(
            "Обчислення виконувалися у центрі обробки даних, а центр мас "
            "визначався за координатами вузлів."
        )

    def test_prose_mentioning_a_university_survives(self):
        self.assert_survives(
            "Similar deployments have been reported by university laboratories "
            "and by industrial research departments across Europe."
        )

    def test_keywords_line_styled_as_authors_survives(self):
        # Templates reuse "Authors Italic" for any italic line, keywords included.
        keywords = "Keywords: software-defined networks; dynamic routing; Q-learning."
        self.builder.add(keywords, "CSN: Authors Italic")
        self.assertIn(keywords, paragraph_texts(self.builder.anonymized()))

    def test_title_styled_as_authors_survives(self):
        title = "DEVELOPMENT OF AN AUTONOMOUS SMART HOME CONTROL SYSTEM"
        self.builder.add(title, "CSN: Authors")
        self.assertIn(title, paragraph_texts(self.builder.anonymized()))

    def test_section_heading_is_not_mined_for_names(self):
        builder = DocumentBuilder()
        front_matter(builder, "© Sovyn Y. R. 2026")
        builder.add("Literature Review")
        builder.add("A review of the literature on scheduling follows.")
        terms = identity_terms(
            *_styled_and_header(builder.document)
        )
        self.assertNotIn("literature", terms)
        self.assertNotIn("review", terms)
        self.assertIn("sovyn", terms)


class HiddenLocationTests(unittest.TestCase):
    """Places Document.paragraphs does not reach."""

    def build(self):
        builder = DocumentBuilder()
        front_matter(builder, "© Sovyn Y. R. 2026")
        return builder

    def test_table_cell_is_redacted(self):
        builder = self.build()
        builder.add_table_cell("Measured by Sovyn using the reference rig.")
        text = full_text(builder.anonymized())
        self.assertNotIn("Sovyn", text)
        self.assertIn("reference rig", text)

    def test_text_box_is_redacted(self):
        builder = self.build()
        builder.add_text_box("Diagram prepared by Sovyn")
        text = full_text(builder.anonymized())
        self.assertNotIn("Sovyn", text)

    def test_running_header_is_cleared(self):
        builder = self.build()
        header = builder.document.sections[0].header
        header.paragraphs[0].text = "Sovyn Y. R. Scheduling method"
        self.assertNotIn("Sovyn", full_text(builder.anonymized()))

    def test_document_properties_are_cleared(self):
        builder = self.build()
        properties = builder.document.core_properties
        properties.author = "Совин Ярослав Романович"
        properties.last_modified_by = "Совин Ярослав Романович"
        properties.title = "Стаття Совина"
        properties.comments = "draft for CSN"
        properties.subject = "scheduling"

        result = builder.anonymized()
        result.seek(0)
        anonymized = Document(result).core_properties
        for name in ("author", "last_modified_by", "title", "comments", "subject"):
            self.assertEqual(getattr(anonymized, name), "", name)
        self.assertNotIn("Совин", full_text(result))


class IdentityPatternTests(unittest.TestCase):
    """The matcher itself: complete words only, in either register."""

    def test_case_ending_is_allowed_but_must_end_the_word(self):
        pattern = identity_pattern({"совин"})
        # A short case ending is part of the name ...
        self.assertEqual(pattern.sub(REDACTED, "Совином"), REDACTED)
        # ... but a longer word that merely starts the same way is left whole,
        # rather than becoming "[anonymized]ЕЛЬ".
        self.assertEqual(pattern.sub(REDACTED, "СОВИНОВІДОМИЙ"), "СОВИНОВІДОМИЙ")

    def test_unrelated_word_with_a_shared_prefix_is_left_alone(self):
        pattern = identity_pattern({"khoma"})
        self.assertEqual(pattern.sub(REDACTED, "khomatography"), "khomatography")

    def test_matching_ignores_register(self):
        pattern = identity_pattern({"sovyn"})
        self.assertEqual(pattern.sub(REDACTED, "SOVYN Sovyn sovyn"), " ".join([REDACTED] * 3))

    def test_no_terms_yields_no_pattern(self):
        self.assertIsNone(identity_pattern(set()))


def _styled_and_header(document):
    """(styled paragraphs, header indices) for a python-docx Document."""
    from docx_processing.extractors import extract_literature
    from pdf_generation.anonymize_and_convert import _header_indices, _styled_view

    elements = list(document.element.body.iter(qn("w:p")))
    styled = _styled_view(elements, document)
    literature = extract_literature([text for text in styled if text])
    return styled, _header_indices(styled, literature)


if __name__ == "__main__":
    unittest.main()
