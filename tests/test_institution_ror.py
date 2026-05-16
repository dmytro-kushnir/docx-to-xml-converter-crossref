import unittest

from xml_generation.crossref.institution_ror import resolve_institution

INSTITUTIONS = {
    "lpnu": {
        "name": "Lviv Polytechnic National University",
        "ror": "https://ror.org/0542q3127",
        "aliases": ["Lviv Polytechnic"],
    },
    "kai": {
        "name": 'State University "Kyiv Aviation Institute"',
        "ror": "https://ror.org/01f74x078",
    },
}


class InstitutionRorTests(unittest.TestCase):
    def test_lpnu_exact(self):
        r = resolve_institution("Lviv Polytechnic National University", INSTITUTIONS)
        self.assertEqual(r["ror"], "https://ror.org/0542q3127")

    def test_department_fallback_to_lpnu(self):
        r = resolve_institution(
            "Department of Electronic Computing Machines",
            INSTITUTIONS,
            default_institution_id="lpnu",
        )
        self.assertEqual(r["name"], "Lviv Polytechnic National University")

    def test_kai_curly_quotes(self):
        r = resolve_institution(
            'State University "Kyiv Aviation Institute"',
            INSTITUTIONS,
        )
        self.assertEqual(r["ror"], "https://ror.org/01f74x078")


if __name__ == "__main__":
    unittest.main()
