import unittest
import xml.etree.ElementTree as ET

from xml_generation.crossref.create_authors import (
    parse_author_name,
    create_xml_for_authors,
)


class ParseAuthorNameTests(unittest.TestCase):
    def test_initials_first(self):
        self.assertEqual(
            parse_author_name("D. I. Prokopovych-Tkachenko"),
            ("D. I.", "Prokopovych-Tkachenko"),
        )
        self.assertEqual(parse_author_name("I.V. Teleshko"), ("I. V.", "Teleshko"))

    def test_surname_first(self):
        self.assertEqual(parse_author_name("Tyshyk I. Y."), ("I. Y.", "Tyshyk"))
        self.assertEqual(parse_author_name("Arseniuk V."), ("V.", "Arseniuk"))

    def test_multi_letter_transliterated_initials(self):
        # 'Yu.', 'Ya.', 'Kh.' are single Cyrillic letters transliterated, and
        # used to be dropped or mangled by a one-letter-only pattern.
        self.assertEqual(parse_author_name("Karpa B. Ya."), ("B. Ya.", "Karpa"))
        self.assertEqual(
            parse_author_name("Nakonechnyi Yu. M."), ("Yu. M.", "Nakonechnyi")
        )
        self.assertEqual(
            parse_author_name("Yu.Ye. Khokhlachova"), ("Yu. Ye.", "Khokhlachova")
        )

    def test_initials_are_always_dotted_and_spaced(self):
        self.assertEqual(parse_author_name("Havrylov D.S."), ("D. S.", "Havrylov"))
        self.assertEqual(parse_author_name("Sovyn Y. R."), ("Y. R.", "Sovyn"))

    def test_cyrillic_bylines(self):
        self.assertEqual(parse_author_name("Хома Ю.В."), ("Ю. В.", "Хома"))
        self.assertEqual(parse_author_name("Ю.В. Хома"), ("Ю. В.", "Хома"))

    def test_full_given_name_and_surname(self):
        self.assertEqual(parse_author_name("Ivan Tyshyk"), ("Ivan", "Tyshyk"))

    def test_three_part_name_is_surname_first(self):
        # Ukrainian style: surname, given name, patronymic.
        self.assertEqual(
            parse_author_name("Bybyk Roman Tarasovych"), ("Roman Tarasovych", "Bybyk")
        )

    def test_empty_input(self):
        self.assertIsNone(parse_author_name(""))
        self.assertIsNone(parse_author_name("Single"))


class ContributorsXmlTests(unittest.TestCase):
    def test_sequence_and_order_follow_the_byline(self):
        root = ET.fromstring(
            create_xml_for_authors("Havrylov D.S., Musienko O.P., Karpa B. Ya.")
        )
        people = root.findall("person_name")
        self.assertEqual([p.get("sequence") for p in people], ["first", "additional", "additional"])
        self.assertEqual(
            [p.findtext("surname") for p in people],
            ["Havrylov", "Musienko", "Karpa"],
        )

    def test_orcids_are_matched_by_position(self):
        root = ET.fromstring(
            create_xml_for_authors(
                "Havrylov D.S., Musienko O.P.",
                author_orcids=["https://orcid.org/0000-0002-9506-014X", None],
            )
        )
        people = root.findall("person_name")
        self.assertEqual(
            people[0].findtext("ORCID"), "https://orcid.org/0000-0002-9506-014X"
        )
        self.assertIsNone(people[1].find("ORCID"))


if __name__ == "__main__":
    unittest.main()
