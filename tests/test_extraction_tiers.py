"""Regression tests for the defects that produced malformed deposits.

Each class here corresponds to a class of article that used to come out wrong:
the CC-BY notice read as the author byline, a reference list truncated to
nothing by a "Literature Review" section heading, an abstract that swallowed the
licence block, and templates whose header does not follow the © line.
"""

import unittest

from docx_processing.extractors import (
    extract_abstract,
    extract_affiliation_lines,
    extract_authors,
    extract_english_title,
    extract_literature,
    extract_ukrainian_title,
)
from docx_processing.parse import StyledText


def styled(text, style="Normal"):
    return StyledText(text, style=style)


def plain(lines):
    return [styled(line) for line in lines]


LICENCE = (
    "© The Author(s). This is an open access article distributed under the terms "
    "of the Creative Commons Attribution License."
)
ABSTRACT_EN = (
    "The paper presents a method for assessing the spatial-frequency situation "
    "and evaluates its accuracy on a set of recorded signals, showing that the "
    "proposed approach outperforms the baseline."
)
ABSTRACT_UA = (
    "У статті запропоновано метод оцінювання просторово-частотної обстановки "
    "та наведено результати його експериментальної перевірки."
)


class CopyrightVersusLicenceTests(unittest.TestCase):
    """The licence notice also starts with '©' — only the wording tells them apart."""

    def test_licence_notice_is_not_the_byline(self):
        paragraphs = plain(
            [
                "УДК 004.7",
                "НАЗВА СТАТТІ УКРАЇНСЬКОЮ МОВОЮ",
                "© Ivanov I.I., Petrov P.P., 2026",
                LICENCE,
            ]
        )
        self.assertEqual(
            extract_authors(paragraphs), "Ivanov I.I., Petrov P.P."
        )

    def test_licence_notice_styled_as_a_byline_is_still_rejected(self):
        # Some templates apply "Authors Italic" to the licence block, so the
        # style must not be used as the discriminator.
        paragraphs = [
            styled("УДК 004.7"),
            styled("НАЗВА СТАТТІ", style="CSN: Article Name"),
            styled(LICENCE, style="CSN: Authors Italic"),
            styled("© Ivanov I.I., 2026"),
        ]
        self.assertEqual(extract_authors(paragraphs), "Ivanov I.I.")

    def test_hand_typed_emphasis_around_the_byline(self):
        paragraphs = plain(
            [
                "УДК 004.7",
                "НАЗВА СТАТТІ УКРАЇНСЬКОЮ МОВОЮ",
                "*© Журавчак Ю. Ю., Журавчак А. Ю., 2026*",
            ]
        )
        self.assertEqual(
            extract_authors(paragraphs, is_ukrainian=True),
            "Журавчак Ю. Ю., Журавчак А. Ю.",
        )

    def test_trailing_year_without_a_comma(self):
        paragraphs = plain(["© Hrytsko T.L., Hlukhov V.S. 2026"])
        self.assertEqual(
            extract_authors(paragraphs), "Hrytsko T.L., Hlukhov V.S."
        )

    def test_affiliation_footnote_digit_is_not_part_of_the_surname(self):
        paragraphs = plain(["© P.P. Petriv1, I.R. Opirskyy2, 2026"])
        self.assertEqual(extract_authors(paragraphs), "P.P. Petriv, I.R. Opirskyy")


class ReferenceHeadingTests(unittest.TestCase):
    def test_section_heading_mentioning_literature_is_not_the_list(self):
        paragraphs = plain(
            [
                "2. Literature Review",
                "Recent work on spectrum sensing has focused on wideband methods.",
                "Список літератури",
                "1. Ivanov I. Some paper. Journal, 2021, pp. 1-10.",
                "2. Petrov P. Another paper. Journal, 2022, pp. 11-20.",
            ]
        )
        references = extract_literature(paragraphs)
        self.assertEqual(len(references), 2)
        self.assertTrue(references[0].startswith("1. Ivanov"))

    def test_styled_references_win_over_text_heuristics(self):
        paragraphs = [
            styled("Список літератури"),
            styled("1. Ivanov I. Paper. 2021.", style="CSN: Literature Sources"),
            styled("2. Petrov P. Paper. 2022.", style="CSN: Literature Sources"),
        ]
        self.assertEqual(len(extract_literature(paragraphs)), 2)

    def test_trailing_author_block_is_not_collected_as_references(self):
        # Reference entries match on years and URLs, so the header that follows
        # the list used to be swallowed by it.
        paragraphs = plain(
            [
                "References",
                "1. Ivanov I. Paper. Journal, 2021, pp. 1-10.",
                "AN ENGLISH TITLE OF THE ARTICLE",
                "© Ivanov I.I., 2026",
                "ORCID: 0000-0002-9506-014X",
            ]
        )
        references = extract_literature(paragraphs)
        self.assertEqual(len(references), 1)


class EnglishHeaderTests(unittest.TestCase):
    def test_header_that_follows_the_copyright_line(self):
        paragraphs = plain(
            [
                "Список літератури",
                "1. Ivanov I. Paper. Journal, 2021, pp. 1-10.",
                "AN ENGLISH TITLE",
                "Ivanov I.I., Petrov P.P.",
                "© Ivanov I.I., Petrov P.P., 2026",
                "Lviv Polytechnic National University, Lviv, Ukraine",
                "ORCID: 0000-0002-9506-014X",
                ABSTRACT_EN,
            ]
        )
        references = extract_literature(paragraphs)
        self.assertEqual(extract_english_title(paragraphs, references), "AN ENGLISH TITLE")
        self.assertIn(
            "Lviv Polytechnic National University, Lviv, Ukraine",
            extract_affiliation_lines(paragraphs, references),
        )

    def test_multi_line_title_is_merged(self):
        paragraphs = plain(
            [
                "References",
                "1. Ivanov I. Paper. Journal, 2021, pp. 1-10.",
                "AN ENGLISH TITLE SPLIT",
                "ACROSS TWO PARAGRAPHS",
                "© Ivanov I.I., 2026",
                ABSTRACT_EN,
            ]
        )
        self.assertEqual(
            extract_english_title(paragraphs, extract_literature(paragraphs)),
            "AN ENGLISH TITLE SPLIT ACROSS TWO PARAGRAPHS",
        )

    def test_per_author_blocks_credit_every_author(self):
        paragraphs = plain(
            [
                "References",
                "1. Ivanov I. Paper. Journal, 2021, pp. 1-10.",
                "AN ENGLISH TITLE",
                "Bybyk Roman Tarasovych",
                "Lviv Polytechnic National University",
                "Department of Information Security",
                "ORCID: 0000-0002-9506-014X",
                "Stakhiv Marta Yuriivna",
                "Lviv Polytechnic National University",
                "Department of Information Security",
                "ORCID: 0000-0002-4094-2081",
            ]
        )
        references = extract_literature(paragraphs)
        self.assertEqual(
            extract_authors(paragraphs, False, references),
            "Bybyk Roman Tarasovych, Stakhiv Marta Yuriivna",
        )

    def test_ukrainian_byline_falls_back_to_the_line_under_the_title(self):
        paragraphs = plain(
            [
                "УДК 621.396",
                "НАЗВА СТАТТІ УКРАЇНСЬКОЮ МОВОЮ ДЛЯ ПЕРЕВІРКИ",
                "Бибик Роман Тарасович",
                "Національний університет «Львівська політехніка»",
                "Кафедра захисту інформації",
                "Стахів Марта Юріївна",
                "Національний університет «Львівська політехніка»",
                "Кафедра захисту інформації",
            ]
        )
        self.assertEqual(
            extract_authors(paragraphs, True),
            "Бибик Роман Тарасович, Стахів Марта Юріївна",
        )


class AbstractBoundaryTests(unittest.TestCase):
    def test_abstract_stops_at_the_keywords_line(self):
        paragraphs = plain(
            ["© Ivanov I.I., 2026", ABSTRACT_EN, "Keywords: one, two, three", "1. Introduction"]
        )
        self.assertEqual(extract_abstract(paragraphs), ABSTRACT_EN)

    def test_licence_and_contact_lines_are_skipped(self):
        paragraphs = plain(
            [
                "© Ivanov I.I., 2026",
                LICENCE,
                "Received: 01.01.2026",
                "e-mail: ivanov@lpnu.ua",
                "ORCID: 0000-0002-9506-014X",
                ABSTRACT_EN,
                "Keywords: one, two",
            ]
        )
        self.assertEqual(extract_abstract(paragraphs), ABSTRACT_EN)

    def test_styled_ukrainian_abstract_does_not_hide_the_english_one(self):
        # When only the Ukrainian abstract carries the style, the styled tier
        # must fall through instead of reporting success with nothing.
        paragraphs = [
            styled(ABSTRACT_UA, style="CSN: Anotation"),
            styled("Ключові слова: один, два", style="CSN: Keywords"),
            styled("© Ivanov I.I., 2026"),
            styled(ABSTRACT_EN),
            styled("Keywords: one, two"),
        ]
        self.assertEqual(extract_abstract(paragraphs), ABSTRACT_EN)

    def test_standalone_abstract_heading_without_a_copyright_line(self):
        paragraphs = plain(
            [
                "AN ENGLISH TITLE",
                "Bybyk Roman Tarasovych",
                "Lviv Polytechnic National University",
                "Abstract",
                ABSTRACT_EN,
                "Keywords: one, two",
            ]
        )
        self.assertEqual(extract_abstract(paragraphs), ABSTRACT_EN)

    def test_leading_abstract_label_is_dropped(self):
        paragraphs = plain(
            ["© Ivanov I.I., 2026", f"Abstract. {ABSTRACT_EN}", "Keywords: one"]
        )
        self.assertEqual(extract_abstract(paragraphs), ABSTRACT_EN)


class TitleScriptTests(unittest.TestCase):
    def test_styled_titles_are_assigned_by_script_not_position(self):
        paragraphs = [
            styled("AN ENGLISH TITLE FIRST", style="CSN: Article Name"),
            styled("НАЗВА СТАТТІ УКРАЇНСЬКОЮ", style="CSN: Article Name"),
        ]
        self.assertEqual(extract_english_title(paragraphs, []), "AN ENGLISH TITLE FIRST")
        self.assertEqual(extract_ukrainian_title(paragraphs), "НАЗВА СТАТТІ УКРАЇНСЬКОЮ")

    def test_english_first_layout_with_untitled_styles(self):
        # Some articles are English-first and leave the *Ukrainian* block after
        # the references. With neither title carrying a title style, taking
        # "the block after the references" as English returned the Cyrillic one.
        references = [
            "1. Author, A. 2024. A cited work. Journal 1 (2): 3-4.",
            "2. Author, B. 2025. Another cited work. Journal 2 (3): 5-6.",
        ]
        paragraphs = plain(
            [
                "УДК 004.938",
                "DEVELOPMENT OF AN AUTONOMOUS CONTROL SYSTEM",
                "M. R. Tabachyshyn, N. E. Kunanets",
                "Lviv Polytechnic National University,",
                "© Tabachyshyn M. R., Kunanets N. E. 2026",
                ABSTRACT_EN,
                "References",
                *references,
                "РОЗРОБКА СИСТЕМИ АВТОНОМНОГО КЕРУВАННЯ",
                "М. Р. Табачишин, Н. Е. Кунанець",
                "Національний університет «Львівська політехніка»",
                "© Табачишин М. Р., Кунанець Н. Е. 2026",
                ABSTRACT_UA,
            ]
        )
        self.assertEqual(
            extract_english_title(paragraphs, extract_literature(paragraphs)),
            "DEVELOPMENT OF AN AUTONOMOUS CONTROL SYSTEM",
        )
        self.assertEqual(
            extract_ukrainian_title(paragraphs),
            "РОЗРОБКА СИСТЕМИ АВТОНОМНОГО КЕРУВАННЯ",
        )


if __name__ == "__main__":
    unittest.main()
