import unittest
import xml.etree.ElementTree as ET

from xml_generation.crossref.create_authors import create_xml_for_authors_with_affiliations

try:
    from xml_generation.crossref.create_crossref_xml import create_full_xml, CROSSREF_SCHEMA_VERSION

    HAS_LXML = True
except ImportError:
    HAS_LXML = False


class Crossref540Tests(unittest.TestCase):
    def test_authors_xml_has_ror_affiliations(self):
        xml = create_xml_for_authors_with_affiliations(
            "Arseniuk V., Partyka A.",
            institution={
                "name": "Lviv Polytechnic National University",
                "ror": "https://ror.org/0542q3127",
            },
            author_orcids=[
                "https://orcid.org/0009-0004-3022-9700",
                "https://orcid.org/0000-0003-3037-8373",
            ],
            department="Department of Information Protection",
        )
        root = ET.fromstring(xml)
        persons = root.findall("person_name")
        self.assertEqual(len(persons), 2)
        self.assertIsNone(root.find("organization"))
        for p in persons:
            children = [c.tag for c in list(p)]
            self.assertLess(children.index("affiliations"), children.index("ORCID"))
            inst = p.find("affiliations/institution")
            name_el = inst.find("institution_name")
            id_el = inst.find("institution_id")
            self.assertIsNotNone(name_el)
            self.assertIsNotNone(id_el)
            self.assertLess(list(inst).index(name_el), list(inst).index(id_el))
            self.assertEqual(id_el.get("type"), "ror")
            self.assertTrue(id_el.text.startswith("https://ror.org/"))
            dept = inst.find("institution_department")
            self.assertIsNotNone(dept)

    @unittest.skipUnless(HAS_LXML, "lxml required for full XML generation")
    def test_full_xml_schema_version(self):
        sample = [
            (
                "SAMPLE TITLE",
                "УКРАЇНСЬКА НАЗВА",
                "Tyshyk I. Y.",
                (1, 10),
                [],
                "Abstract text.",
                ["Lviv Polytechnic National University", "Department of Information Protection"],
                ["https://orcid.org/0000-0003-1465-5342"],
            )
        ]
        out = create_full_xml(sample)
        self.assertIn(f'version="{CROSSREF_SCHEMA_VERSION}"', out)
        self.assertIn("http://www.crossref.org/schema/5.4.0", out)
        self.assertIn("institution_id", out)
        self.assertNotRegex(out, r"<organization\s")


if __name__ == "__main__":
    unittest.main()
