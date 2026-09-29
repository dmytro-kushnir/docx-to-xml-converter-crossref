import unittest

from docx_processing.article import ArticleRecord
from docx_validation.article_validator import (
    ERROR,
    WARNING,
    format_institution_stub,
    has_errors,
    unmapped_institutions,
    validate_article,
    validate_articles,
)

INSTITUTIONS = {
    "lpnu": {
        "name": "Lviv Polytechnic National University",
        "ror": "https://ror.org/0542q3127",
    }
}

ABSTRACT = (
    "The paper presents a method for assessing the spatial-frequency situation "
    "and evaluates its accuracy on a set of recorded signals."
)


def record(**overrides):
    """A record with no defects, so each test can introduce exactly one."""
    defaults = dict(
        filename="Article.docx",
        english_title="A PERFECTLY GOOD ENGLISH TITLE",
        ukrainian_title="ЦІЛКОМ ПРИСТОЙНА НАЗВА СТАТТІ",
        authors="Ivanov I.I., Petrov P.P.",
        ukrainian_authors="Іванов І.І., Петров П.П.",
        start_page=10,
        end_page=25,
        literature=["1. Ivanov I. Paper. 2021.", "2. Petrov P. Paper. 2022.", "3. X. 2023."],
        abstract=ABSTRACT,
        affiliation_lines=["Lviv Polytechnic National University"],
        author_orcids=[
            "https://orcid.org/0000-0002-9506-014X",
            "https://orcid.org/0000-0002-4094-2081",
        ],
    )
    defaults.update(overrides)
    return ArticleRecord(**defaults)


def codes(findings, severity=None):
    return sorted(
        f.code for f in findings if severity is None or f.severity == severity
    )


class CleanArticleTests(unittest.TestCase):
    def test_a_well_formed_article_produces_no_findings(self):
        self.assertEqual(validate_article(record(), INSTITUTIONS), [])


class BlockingDefectTests(unittest.TestCase):
    def test_extractor_gave_up(self):
        findings = validate_article(
            record(
                english_title="English title not found.",
                authors="Authors not found.",
                abstract="Abstract not found.",
                literature=[],
            ),
            INSTITUTIONS,
        )
        self.assertEqual(
            codes(findings, ERROR),
            ["abstract", "authors", "english-title", "references"],
        )

    def test_template_placeholder_byline(self):
        findings = validate_article(
            record(authors="[Author surname(s) and initials]"), INSTITUTIONS
        )
        self.assertEqual(codes(findings, ERROR), ["authors"])

    def test_licence_notice_read_as_the_byline(self):
        findings = validate_article(
            record(
                authors=(
                    "The Author(s). This is an open access article distributed under "
                    "the Creative Commons Attribution License."
                )
            ),
            INSTITUTIONS,
        )
        self.assertEqual(codes(findings, ERROR), ["authors"])

    def test_cyrillic_english_title(self):
        findings = validate_article(
            record(english_title="РОЗРОБКА СИСТЕМИ КЕРУВАННЯ"), INSTITUTIONS
        )
        self.assertEqual(codes(findings, ERROR), ["english-title"])

    def test_identical_titles(self):
        findings = validate_article(
            record(english_title="SAME TITLE", ukrainian_title="SAME TITLE"),
            INSTITUTIONS,
        )
        self.assertIn("english-title", codes(findings, ERROR))

    def test_missing_affiliation(self):
        findings = validate_article(record(affiliation_lines=[]), INSTITUTIONS)
        self.assertEqual(codes(findings, ERROR), ["affiliation"])

    def test_default_institution_would_misattribute_the_ror(self):
        findings = validate_article(
            record(affiliation_lines=["V. N. Karazin Kharkiv National University"]),
            INSTITUTIONS,
            default_institution_id="lpnu",
        )
        self.assertEqual(codes(findings, ERROR), ["institution-ror"])


class AdvisoryFindingTests(unittest.TestCase):
    def test_unmapped_institution_without_a_default_is_only_a_warning(self):
        findings = validate_article(
            record(affiliation_lines=["V. N. Karazin Kharkiv National University"]),
            INSTITUTIONS,
        )
        self.assertEqual(codes(findings, ERROR), [])
        self.assertEqual(codes(findings, WARNING), ["institution-ror"])

    def test_missing_orcids(self):
        findings = validate_article(record(author_orcids=[None, None]), INSTITUTIONS)
        self.assertEqual(codes(findings, WARNING), ["orcid"])

    def test_byline_lengths_disagree(self):
        findings = validate_article(
            record(ukrainian_authors="Іванов І.І."), INSTITUTIONS
        )
        self.assertEqual(codes(findings, WARNING), ["authors"])

    def test_short_abstract(self):
        findings = validate_article(record(abstract="Too short."), INSTITUTIONS)
        self.assertEqual(codes(findings, WARNING), ["abstract"])

    def test_page_defects_never_block(self):
        # Pages stay provisional until the typeset PDF exists, so they must not
        # stop a run no matter how implausible they look.
        for start, end in ((1, 1), (0, 0), (20, 5), (1, 500)):
            findings = validate_article(
                record(start_page=start, end_page=end), INSTITUTIONS
            )
            self.assertEqual(codes(findings, ERROR), [], f"{start}-{end}")
            self.assertEqual(codes(findings, WARNING), ["pages"], f"{start}-{end}")


class BatchReportingTests(unittest.TestCase):
    def test_has_errors_is_driven_by_error_severity_only(self):
        results = validate_articles(
            [record(filename="a.docx"), record(filename="b.docx", author_orcids=[])],
            INSTITUTIONS,
        )
        self.assertFalse(has_errors(results))

        results = validate_articles(
            [record(filename="c.docx", authors="Authors not found.")], INSTITUTIONS
        )
        self.assertTrue(has_errors(results))

    def test_unmapped_institutions_are_deduplicated_in_order(self):
        records = [
            record(filename="a.docx", affiliation_lines=["University of Customs and Finance"]),
            record(filename="b.docx", affiliation_lines=["University of Customs and Finance"]),
            record(filename="c.docx", affiliation_lines=["Lviv Polytechnic National University"]),
            record(filename="d.docx", affiliation_lines=["V. N. Karazin Kharkiv National University"]),
        ]
        self.assertEqual(
            unmapped_institutions(records, INSTITUTIONS),
            [
                "University of Customs and Finance",
                "V. N. Karazin Kharkiv National University",
            ],
        )

    def test_institution_stub_is_yaml_shaped(self):
        stub = format_institution_stub(["University of Customs and Finance"])
        self.assertIn('name: "University of Customs and Finance"', stub)
        self.assertIn('ror: ""', stub)
        self.assertEqual(format_institution_stub([]), "")


class TupleConversionTests(unittest.TestCase):
    def test_to_tuple_matches_the_xml_generator_contract(self):
        article = record()
        self.assertEqual(
            article.to_tuple(),
            (
                article.english_title,
                article.ukrainian_title,
                article.authors,
                (10, 25),
                article.literature,
                article.abstract,
                article.affiliation_lines,
                article.author_orcids,
            ),
        )


if __name__ == "__main__":
    unittest.main()
