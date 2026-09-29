import unittest
import xml.etree.ElementTree as ET

from docx_processing.article import ArticleRecord
from xml_generation.ici_copernicus.create_copernicus_ini_xml import (
    create_ici_copernicus_xml,
    parse_authors_simple,
)


def article_tuple(**overrides):
    defaults = {
        "english_title": "A SURVEY OF EDGE INFERENCE",
        "ukrainian_title": "ОГЛЯД ГРАНИЧНОГО ВИВЕДЕННЯ",
        "authors": "Havrylov D.S., Musienko O.P.",
        "start_page": 1,
        "end_page": 12,
        "literature": ["Some reference. https://doi.org/10.1000/xyz123"],
        "abstract": "The English abstract.",
        "ukrainian_abstract": "Український текст анотації.",
        "english_keywords": ["edge inference", "latency"],
        "ukrainian_keywords": ["граничне виведення", "затримка"],
        "affiliation_lines": ["Lviv Polytechnic National University"],
    }
    defaults.update(overrides)
    return ArticleRecord(filename="a.docx", **defaults)


def language_versions(xml_text):
    article = ET.fromstring(xml_text.split("?>", 1)[1]).find("./issue/article")
    return {lv.get("language"): lv for lv in article.findall("languageVersion")}


class LanguagePayloadTests(unittest.TestCase):
    def test_both_languages_get_their_own_abstract_and_keywords(self):
        record = article_tuple()
        xml_text = create_ici_copernicus_xml(
            [record.to_tuple()], [record.language_payload()]
        )
        versions = language_versions(xml_text)

        self.assertEqual(versions["en"].findtext("abstract"), "The English abstract.")
        self.assertEqual(
            versions["uk"].findtext("abstract"), "Український текст анотації."
        )
        self.assertEqual(
            [k.text for k in versions["en"].findall("./keywords/keyword")],
            ["edge inference", "latency"],
        )
        self.assertEqual(
            [k.text for k in versions["uk"].findall("./keywords/keyword")],
            ["граничне виведення", "затримка"],
        )

    def test_without_a_payload_the_english_abstract_is_still_deposited(self):
        # Backwards-compatible path: no per-language data available.
        record = article_tuple()
        versions = language_versions(create_ici_copernicus_xml([record.to_tuple()]))
        self.assertEqual(versions["en"].findtext("abstract"), "The English abstract.")
        self.assertIsNone(versions["uk"].find("abstract"))

    def test_misaligned_payload_list_is_refused(self):
        # Silently zipping the shorter list would attach one article's abstract
        # to another article's DOI.
        with self.assertRaises(ValueError):
            create_ici_copernicus_xml([article_tuple().to_tuple()], [])


class CopernicusAuthorTests(unittest.TestCase):
    def test_initials_are_dotted_like_the_crossref_deposit(self):
        self.assertEqual(
            parse_authors_simple("Havrylov D.S., Karpa B. Ya."),
            [
                {
                    "name": "D. S.",
                    "surname": "Havrylov",
                    "order": "1",
                    "role": "AUTHOR",
                    "polishAffiliation": "false",
                },
                {
                    "name": "B. Ya.",
                    "surname": "Karpa",
                    "order": "2",
                    "role": "AUTHOR",
                    "polishAffiliation": "false",
                },
            ],
        )

    def test_affiliation_is_attached_to_every_author(self):
        record = article_tuple()
        xml_text = create_ici_copernicus_xml(
            [record.to_tuple()], [record.language_payload()]
        )
        article = ET.fromstring(xml_text.split("?>", 1)[1]).find("./issue/article")
        affiliations = [
            a.findtext("instituteAffiliation") for a in article.findall("./authors/author")
        ]
        self.assertEqual(
            affiliations, ["Lviv Polytechnic National University"] * 2
        )


class ReferenceTests(unittest.TestCase):
    def test_reference_doi_is_extracted(self):
        record = article_tuple()
        xml_text = create_ici_copernicus_xml(
            [record.to_tuple()], [record.language_payload()]
        )
        article = ET.fromstring(xml_text.split("?>", 1)[1]).find("./issue/article")
        self.assertEqual(
            article.findtext("./references/reference/doi"), "10.1000/xyz123"
        )


if __name__ == "__main__":
    unittest.main()
