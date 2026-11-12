"""The DOI-registration sheet must keep the exact layout of the agency's template.

It is generated from docx_generation/templates/doi_letter_template.docx, so the
tests check two things: the issue's data lands in the right cells, and every
article row is formatted exactly like the template's prototype row.
"""

import os
import re
import tempfile
import unittest

from docx import Document
from lxml import etree

from docx_generation.generate_docx import (
    DOI_LETTER_TEMPLATE,
    _initials,
    create_doi_letter_docx,
)

CROSSREF_XML = """<?xml version="1.0" encoding="UTF-8"?>
<doi_batch xmlns="http://www.crossref.org/schema/5.4.0" version="5.4.0">
  <body><journal>
    <journal_metadata>
      <full_title>Computer systems and networks</full_title>
      <abbrev_title>CSN</abbrev_title>
      <issn media_type="print">27072371</issn>
      <doi_data><doi>10.23939/csn</doi><resource>https://science.lpnu.ua/csn</resource></doi_data>
    </journal_metadata>
    <journal_issue>
      <publication_date media_type="print"><month>12</month><year>2026</year></publication_date>
      <journal_volume><volume>8</volume></journal_volume>
      <issue>2</issue>
      <doi_data><doi>10.23939/csn2026.02</doi>
        <resource>https://science.lpnu.ua/csn/all-volumes-and-issues/volume-8-number-2-2026</resource></doi_data>
    </journal_issue>
    <journal_article>
      <titles><title>First article title</title></titles>
      <contributors>
        <person_name sequence="first" contributor_role="author"><given_name>D. S.</given_name><surname>Havrylov</surname></person_name>
        <person_name sequence="additional" contributor_role="author"><given_name>Volodymyr</given_name><surname>Pavlenko</surname></person_name>
      </contributors>
      <pages><first_page>1</first_page><last_page>12</last_page></pages>
      <doi_data><doi>10.23939/csn2026.02.001</doi><resource>https://science.lpnu.ua/csn/a/first</resource></doi_data>
    </journal_article>
    <journal_article>
      <titles><title>SECOND ARTICLE</title></titles>
      <contributors>
        <person_name sequence="first" contributor_role="author"><given_name>M. Yu.</given_name><surname>Shcherba</surname></person_name>
      </contributors>
      <pages><first_page>13</first_page><last_page>20</last_page></pages>
      <doi_data><doi>10.23939/csn2026.02.013</doi><resource>https://science.lpnu.ua/csn/a/second</resource></doi_data>
    </journal_article>
  </journal></body>
</doi_batch>
"""


def _skeleton(element):
    """Row XML with the text and Word's revision ids removed: pure formatting."""
    xml = etree.tostring(element, encoding="unicode")
    # Any text node — filled, emptied, with or without xml:space — is the same node.
    xml = re.sub(r"<w:t(?: [^>]*)?(?:/>|>[^<]*</w:t>)", "<w:t/>", xml)
    return re.sub(r' w14:(?:paraId|textId)="[^"]+"', "", xml)


class DoiLetterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        xml_path = os.path.join(cls.tmp.name, "CSN 8 #2.xml")
        with open(xml_path, "w", encoding="utf-8") as handle:
            handle.write(CROSSREF_XML)
        cls.output = os.path.join(cls.tmp.name, "doi_letter.docx")
        create_doi_letter_docx(
            xml_path, cls.output,
            journal_title_uk="Комп’ютерні системи та мережі",
            journal_url="https://science.lpnu.ua/csn",
        )
        cls.doc = Document(cls.output)
        cls.template = Document(DOI_LETTER_TEMPLATE)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_issue_line_appears_in_both_headers(self):
        lines = [p.text for p in self.doc.paragraphs]
        expected = "Випуск 8, №2, 2026 рік (Volume 8, Number 2, 2026)"
        self.assertEqual(lines.count(expected), 2)
        self.assertIn("(Computer systems and networks)", lines)

    def test_journal_table_values(self):
        values = {row.cells[0].text.strip()[:12]: row.cells[1].text.strip() for row in self.doc.tables[0].rows}
        self.assertEqual(values["ISSN"], "2707-2371")
        self.assertEqual(values["Число журнал"], "Volume 8, Number 2")
        self.assertEqual(values["Рік видання"], "2026")
        self.assertEqual(values["Скорочена на"], "CSN")
        self.assertEqual(values["Назва відпов"], "Комп’ютерні системи та мережі")

    def test_hyperlinks_point_at_this_issue(self):
        targets = {rel._target for rel in self.doc.part.rels.values() if "hyperlink" in rel.reltype}
        self.assertEqual(targets, {
            "https://science.lpnu.ua/csn",
            "https://science.lpnu.ua/csn/all-volumes-and-issues/volume-8-number-2-2026",
        })

    def test_article_rows(self):
        rows = self.doc.tables[1].rows[1:]
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            [cell.text for cell in rows[0].cells],
            ["1", "D.S. Havrylov, V. Pavlenko. FIRST ARTICLE TITLE\nhttps://science.lpnu.ua/csn/a/first", "1-12"],
        )
        self.assertEqual(rows[1].cells[1].text.split("\n")[0], "M.Yu. Shcherba. SECOND ARTICLE")
        self.assertEqual(rows[1].cells[2].text, "13-20")

    def test_rows_keep_the_template_formatting(self):
        prototype = _skeleton(self.template.tables[1].rows[1]._tr)
        for row in self.doc.tables[1].rows[1:]:
            self.assertEqual(_skeleton(row._tr), prototype)

    def test_layout_outside_the_article_rows_is_untouched(self):
        # Header paragraphs and the journal table differ from the template only in text.
        generated = [_skeleton(p._p) for p in self.doc.paragraphs]
        template = [_skeleton(p._p) for p in self.template.paragraphs]
        self.assertEqual(generated, template)
        self.assertEqual(_skeleton(self.doc.tables[0]._tbl), _skeleton(self.template.tables[0]._tbl))


class InitialsTests(unittest.TestCase):
    def test_spaced_initials_are_closed_up(self):
        self.assertEqual(_initials("D. S."), "D.S.")

    def test_full_given_name_becomes_an_initial(self):
        self.assertEqual(_initials("Volodymyr"), "V.")

    def test_two_letter_initials_are_kept(self):
        self.assertEqual(_initials("M. Yu."), "M.Yu.")

    def test_hyphenated_given_name(self):
        self.assertEqual(_initials("Anna-Maria"), "A.-M.")


if __name__ == "__main__":
    unittest.main()
