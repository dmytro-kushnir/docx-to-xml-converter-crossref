"""Tests for the editorial-date editor.

The dangerous cases are all about *not* losing information: a placeholder must
never overwrite a date someone filled in, a half-filled "ХХ.ХХ.2026" must keep
its year, and a second run must be a no-op so that re-running never rewrites
work (or, in --in-place mode, backs up already-edited files as "originals").
"""

import unittest

from docx_editing.add_submission_dates import (
    LABELS,
    PLACEHOLDER,
    _paragraphs,
    found_dates,
    plan_insertions,
    plan_updates,
)

LICENCE = (
    "© The Author(s). This is an open access article distributed under the "
    "terms of the Creative Commons Attribution License."
)
PLACEHOLDERS = (PLACEHOLDER, PLACEHOLDER, PLACEHOLDER)
REAL = ("15.09.2026", "20.10.2026", "01.12.2026")


def paragraph(text, style="CSN: Authors emails"):
    props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
    runs = f"<w:r><w:rPr><w:i/><w:lang w:val=\"en-US\"/></w:rPr><w:t>{text}</w:t></w:r>"
    return f"<w:p>{props}{runs}</w:p>"


def document(*texts):
    return (
        '<?xml version="1.0"?><w:document><w:body>'
        + "".join(paragraph(text) for text in texts)
        + "</w:body></w:document>"
    )


def date_line(language, values):
    return "".join(
        f"{label}: {value}" for label, value in zip(LABELS[language], values)
    )


def author_block(language, dates=None, byline="© Sovyn Y. R. 2026"):
    lines = ["Y. R. Sovyn", "Lviv Polytechnic National University", "E-mail: a@b.ua",
             "ORCID: 0000-0001-5436-721X"]
    if dates:
        lines.append(date_line(language, dates))
    lines.append(byline)
    return lines


class FoundDatesTests(unittest.TestCase):
    """The three lines share one paragraph, run together without separators."""

    def test_reads_all_three_labels_from_one_line(self):
        language, hits = found_dates(date_line("en", REAL))
        self.assertEqual(language, "en")
        self.assertEqual([value for _, _, value in hits], list(REAL))

    def test_reads_a_ukrainian_line(self):
        language, hits = found_dates(date_line("uk", PLACEHOLDERS))
        self.assertEqual(language, "uk")
        self.assertEqual([label for _, label, _ in hits], list(LABELS["uk"]))

    def test_reads_a_single_label_on_its_own_paragraph(self):
        language, hits = found_dates("Опубліковано: 01.12.2026")
        self.assertEqual(language, "uk")
        self.assertEqual(hits, [(2, "Опубліковано", "01.12.2026")])

    def test_prose_mentioning_published_is_not_a_date_line(self):
        self.assertEqual(found_dates("Published: results of the survey"), (None, []))


class UpdateTests(unittest.TestCase):
    def plan(self, existing, dates, overwrite=False):
        xml = document(date_line("en", existing))
        return plan_updates(_paragraphs(xml), dates, overwrite)

    def applied(self, existing, dates, overwrite=False):
        edits = self.plan(existing, dates, overwrite)
        if not edits:
            return list(existing)
        _, _, fragment, _ = edits[0]
        return [value for _, _, value in found_dates(_paragraphs(fragment)[0][3])[1]]

    def test_real_date_fills_a_placeholder(self):
        self.assertEqual(self.applied(PLACEHOLDERS, REAL), list(REAL))

    def test_placeholder_never_overwrites_a_real_date(self):
        existing = ("15.09.2026", "20.10.2026", "01.12.2026")
        self.assertEqual(self.plan(existing, PLACEHOLDERS), [])

    def test_placeholder_never_discards_a_known_year(self):
        # "ХХ.ХХ.2026" is still a placeholder, but its year is information.
        existing = ("ХХ.ХХ.2026", "ХХ.ХХ.2026", "ХХ.ХХ.2026")
        self.assertEqual(self.plan(existing, PLACEHOLDERS), [])

    def test_existing_date_outranks_the_issue_wide_value(self):
        existing = ("25.08.2025", PLACEHOLDER, PLACEHOLDER)
        self.assertEqual(self.applied(existing, REAL), ["25.08.2025", REAL[1], REAL[2]])

    def test_overwrite_existing_replaces_a_real_date(self):
        existing = ("25.08.2025", PLACEHOLDER, PLACEHOLDER)
        self.assertEqual(self.applied(existing, REAL, overwrite=True), list(REAL))

    def test_no_edit_planned_when_nothing_changes(self):
        self.assertEqual(self.plan(REAL, REAL), [])

    def test_update_keeps_the_paragraph_formatting(self):
        edits = self.plan(PLACEHOLDERS, REAL)
        self.assertIn('<w:pStyle w:val="CSN: Authors emails"/>', edits[0][2])
        self.assertIn("<w:i/>", edits[0][2])
        # Two line breaks, so the three lines still render as three lines.
        self.assertEqual(edits[0][2].count("<w:br/>"), 2)


class InsertionTests(unittest.TestCase):
    def test_block_is_inserted_after_the_contact_line(self):
        xml = document(*author_block("uk", byline="© Совин Я. Р. 2026"))
        paragraphs = _paragraphs(xml)
        edits = plan_insertions(paragraphs, PLACEHOLDERS)
        self.assertEqual(len(edits), 1)
        offset, _, fragment, language = edits[0]
        self.assertEqual(language, "uk")
        # Directly after the ORCID line, i.e. just before the © byline.
        self.assertEqual(offset, paragraphs[3][1])
        self.assertIn("Надійшла до редакції", fragment)

    def test_nothing_inserted_when_the_block_is_already_there(self):
        xml = document(*author_block("uk", PLACEHOLDERS, byline="© Совин Я. Р. 2026"))
        self.assertEqual(plan_insertions(_paragraphs(xml), PLACEHOLDERS), [])

    def test_licence_notice_is_not_treated_as_a_byline(self):
        # The CC-BY notice is a © paragraph too, and a Latin one; expanding
        # around it drops an English block into the Ukrainian author block.
        xml = document(*author_block("uk", PLACEHOLDERS, byline="© Совин Я. Р. 2026"),
                       "Вступ", LICENCE)
        self.assertEqual(plan_insertions(_paragraphs(xml), PLACEHOLDERS), [])

    def test_both_language_blocks_get_their_own_dates(self):
        xml = document(
            *author_block("uk", byline="© Совин Я. Р. 2026"),
            "Вступ",
            *author_block("en", byline="© Sovyn Y. R. 2026"),
        )
        edits = plan_insertions(_paragraphs(xml), PLACEHOLDERS)
        self.assertEqual([language for _, _, _, language in edits], ["uk", "en"])

    def test_inserted_block_carries_the_right_spellcheck_locale(self):
        xml = document(*author_block("uk", byline="© Совин Я. Р. 2026"))
        fragment = plan_insertions(_paragraphs(xml), PLACEHOLDERS)[0][2]
        self.assertIn('w:val="uk-UA"', fragment)
        self.assertNotIn('w:val="en-US"', fragment)


class IdempotencyTests(unittest.TestCase):
    """A second run must be a no-op, including in --in-place mode."""

    def test_inserting_then_replanning_finds_nothing(self):
        xml = document(*author_block("uk", byline="© Совин Я. Р. 2026"))
        paragraphs = _paragraphs(xml)
        offset, end, fragment, _ = plan_insertions(paragraphs, REAL)[0]
        updated = xml[:offset] + fragment + xml[end:]

        again = _paragraphs(updated)
        self.assertEqual(plan_insertions(again, REAL), [])
        self.assertEqual(plan_updates(again, REAL, False), [])


if __name__ == "__main__":
    unittest.main()
