import unittest

from docx_processing.styles import (
    has_role,
    paragraph_role,
    paragraphs_with_role,
    style_family,
    style_role,
    template_families,
)
from docx_processing.parse import StyledText


class StyleFamilyTests(unittest.TestCase):
    def test_family_is_the_template_prefix(self):
        self.assertEqual(style_family("CSN: Literature Sources"), "CSN")
        self.assertEqual(style_family("CSN SOT: Anotation"), "CSN SOT")
        self.assertEqual(style_family("ACPS: Text"), "ACPS")

    def test_builtin_styles_have_no_family(self):
        self.assertEqual(style_family("Normal"), "")
        self.assertEqual(style_family(""), "")
        self.assertEqual(style_family(None), "")


class StyleRoleTests(unittest.TestCase):
    def test_roles_ignore_the_template_prefix(self):
        self.assertEqual(style_role("CSN: Literature Sources"), "references")
        self.assertEqual(style_role("CSN SOT: Literature Sources"), "references")
        self.assertEqual(style_role("Bibliography"), "references")

    def test_narrower_author_styles_win_over_plain_authors(self):
        # "Authors emails" and "Authors Italic" both contain "Authors"; if the
        # broad rule won, e-mail and copyright lines would be read as bylines.
        self.assertEqual(style_role("CSN: Authors emails"), "email")
        self.assertEqual(style_role("CSN: Authors Italic"), "copyright")
        self.assertEqual(style_role("CSN: Authors"), "authors")

    def test_abstract_and_keyword_styles(self):
        self.assertEqual(style_role("CSN: Anotation"), "abstract")
        self.assertEqual(style_role("CSN: Keywords"), "keywords")

    def test_unknown_style_has_no_role(self):
        self.assertEqual(style_role("ACPS: Text"), "")
        self.assertEqual(style_role("Normal"), "")
        self.assertEqual(style_role(""), "")


class ParagraphRoleTests(unittest.TestCase):
    def setUp(self):
        self.paragraphs = [
            StyledText("A TITLE", style="CSN: Article Name"),
            StyledText("Ivanov I.I.", style="CSN: Authors"),
            StyledText("Some prose", style="Normal"),
            StyledText("1. Reference one", style="CSN: Literature Sources"),
        ]

    def test_role_of_plain_string_is_empty(self):
        self.assertEqual(paragraph_role("plain text"), "")

    def test_paragraphs_with_role_keeps_document_order(self):
        self.assertEqual(
            [str(p) for p in paragraphs_with_role(self.paragraphs, "title", "authors")],
            ["A TITLE", "Ivanov I.I."],
        )

    def test_has_role(self):
        self.assertTrue(has_role(self.paragraphs, "references"))
        self.assertFalse(has_role(self.paragraphs, "orcid"))

    def test_template_families_are_reported_for_diagnostics(self):
        self.assertEqual(template_families(self.paragraphs), ["CSN"])


class StyledTextTests(unittest.TestCase):
    def test_behaves_as_a_plain_string(self):
        paragraph = StyledText("© Ivanov I.I., 2026", style="CSN: Authors Italic")
        self.assertTrue(paragraph.startswith("©"))
        self.assertEqual(paragraph, "© Ivanov I.I., 2026")
        self.assertIn("Ivanov", paragraph)

    def test_carries_style_metadata(self):
        paragraph = StyledText("text", style="CSN: Anotation", bold=True, size=9.0)
        self.assertEqual(paragraph.family, "CSN")
        self.assertEqual(paragraph.role, "abstract")
        self.assertTrue(paragraph.bold)
        self.assertEqual(paragraph.size, 9.0)


if __name__ == "__main__":
    unittest.main()
