import unittest

from docx_processing.extractors import (
    align_author_orcids,
    extract_orcids_from_comma_separated_line,
    extract_orcids_from_text,
    _line_is_comma_separated_orcid_list,
    normalize_orcid_url,
)


class OrcidExtractionTests(unittest.TestCase):
    def test_bare_orcid_ending_in_x(self):
        oid = "0009-0000-5717-945X"
        self.assertEqual(
            extract_orcids_from_text(oid),
            ["https://orcid.org/0009-0000-5717-945X"],
        )
        self.assertEqual(
            normalize_orcid_url(oid),
            "https://orcid.org/0009-0000-5717-945X",
        )

    def test_comma_separated_list_from_journal(self):
        line = (
            "0000-0002-3156-3475, 0009-0000-5717-945X, "
            "0000-0001-5272-8703, 0000-0002-6875-8534"
        )
        self.assertTrue(_line_is_comma_separated_orcid_list(line))
        urls = extract_orcids_from_comma_separated_line(line)
        self.assertEqual(len(urls), 4)
        self.assertIn("945X", urls[1])

    def test_align_four_authors(self):
        authors = "Havano O. V., Dobush P. V., Herych O. V., Shakhovska N. B."
        raw = extract_orcids_from_comma_separated_line(
            "0000-0002-3156-3475, 0009-0000-5717-945X, "
            "0000-0001-5272-8703, 0000-0002-6875-8534"
        )
        aligned = align_author_orcids(authors, raw)
        self.assertEqual(len(aligned), 4)
        self.assertEqual(aligned[1], "https://orcid.org/0009-0000-5717-945X")

    def test_inline_url_orcid(self):
        line = (
            "Havano I. V. (https://orcid.org/0000-0002-3156-3475), Dobush A. P."
        )
        found = extract_orcids_from_text(line)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0], "https://orcid.org/0000-0002-3156-3475")


if __name__ == "__main__":
    unittest.main()
