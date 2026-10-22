import unittest

from xml_generation.crossref.institution_ror import load_institutions, resolve_institution

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


class RegistryFileTests(unittest.TestCase):
    """The real institutions.yml, which the fixtures above do not cover.

    Matching is deliberately loose (substring either way), so a newly added
    alias can silently capture another university's affiliation lines. That
    would deposit the wrong ROR, which is worth catching here rather than at
    the registry.
    """

    @classmethod
    def setUpClass(cls):
        cls.registry = load_institutions()

    def test_registry_loads(self):
        self.assertTrue(self.registry, "institutions.yml is missing or empty")

    def test_every_entry_has_a_name_and_a_plausible_ror(self):
        for key, entry in self.registry.items():
            self.assertTrue(entry.get("name"), f"{key} has no name")
            ror = entry.get("ror", "")
            # "" is legitimate: it marks one a human still has to look up.
            if ror:
                self.assertRegex(ror, r"^https://ror\.org/[0-9a-z]+$", f"{key}: {ror!r}")

    def test_every_name_and_alias_resolves_to_its_own_entry(self):
        for key, entry in self.registry.items():
            for line in [entry["name"], *(entry.get("aliases") or [])]:
                resolved = resolve_institution(line, self.registry)
                self.assertIsNotNone(resolved, f"{key}: {line!r} resolves to nothing")
                self.assertEqual(
                    resolved["name"],
                    entry["name"],
                    f"{key}: {line!r} resolves to {resolved['name']!r} instead",
                )
