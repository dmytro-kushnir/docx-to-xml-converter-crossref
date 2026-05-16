import unittest

from docx_processing.extractors import affiliation_lines_for_crossref_organization


class AffiliationLinesForCrossrefTests(unittest.TestCase):
    def test_university_only_skips_department(self):
        lines = [
            "Lviv Polytechnic National University",
            "Department of Information Protection",
            "12, Bandery St., Lviv, Ukraine",
        ]
        self.assertEqual(
            affiliation_lines_for_crossref_organization(lines),
            ["Lviv Polytechnic National University"],
        )

    def test_first_top_level_when_department_not_first(self):
        lines = [
            "Department of Electronic Computing Machines",
            "Lviv Polytechnic National University",
        ]
        self.assertEqual(
            affiliation_lines_for_crossref_organization(lines),
            ["Lviv Polytechnic National University"],
        )

    def test_fallback_to_first_line_if_only_department(self):
        lines = ["Department of Electronic Computing Machines"]
        self.assertEqual(
            affiliation_lines_for_crossref_organization(lines),
            ["Department of Electronic Computing Machines"],
        )


if __name__ == "__main__":
    unittest.main()
