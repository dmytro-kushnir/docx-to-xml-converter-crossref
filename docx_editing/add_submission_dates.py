"""Fill in the editorial submission dates across a folder of articles.

Every article carries three editorial dates under its author block, once per
language::

    Надійшла до редакції: ХХ.ХХ.ХХХХ      Received: ХХ.ХХ.ХХХХ
    Прийнята до друку: ХХ.ХХ.ХХХХ         Accepted: ХХ.ХХ.ХХХХ
    Опубліковано: ХХ.ХХ.ХХХХ              Published: ХХ.ХХ.ХХХХ

This does two things, driven by ``config.yml`` → ``submission_dates``:

* **inserts** the block in articles that arrived without it, or with only the
  Ukrainian half;
* **fills in** the ``ХХ.ХХ.ХХХХ`` placeholders in the articles that have it.

A date already filled in is left alone unless ``overwrite_existing`` is set, so
a per-article acceptance date is never clobbered by the issue-wide value.

The edit is done on the raw ``word/document.xml`` text rather than through
python-docx, and every other part of the package is copied byte for byte, so
the only possible difference is in the date paragraphs themselves. An article
that needs no change is copied (or left) untouched, byte for byte.

Placement and formatting both come from the document itself: an inserted block
goes directly after the last contact line (e-mail / ORCID) above a © byline,
and reuses that line's own paragraph and run properties, so it inherits
whichever template the submission was written in.

    python -m docx_editing.add_submission_dates              # -> articles_with_dates/
    python -m docx_editing.add_submission_dates --dry-run    # report only
    python -m docx_editing.add_submission_dates --in-place   # edit the input folder
"""

import argparse
import datetime
import os
import re
import shutil
import zipfile

import yaml

from docx_processing.extractors import (
    CYRILLIC_RE,
    LICENSE_NOTICE_RE,
    starts_with_copyright,
)

DEFAULT_OUTPUT = "articles_with_dates"
PLACEHOLDER = "ХХ.ХХ.ХХХХ"
CONFIG_SECTION = "submission_dates"
FIELDS = ("received", "accepted", "published")

LABELS = {
    "uk": ("Надійшла до редакції", "Прийнята до друку", "Опубліковано"),
    "en": ("Received", "Accepted", "Published"),
}

PARAGRAPH_RE = re.compile(r"<w:p(?:\s[^>]*)?(?:/>|>.*?</w:p>)", re.DOTALL)
TEXT_NODE_RE = re.compile(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>", re.DOTALL)
PARAGRAPH_PROPS_RE = re.compile(r"<w:pPr>.*?</w:pPr>", re.DOTALL)
RUN_PROPS_RE = re.compile(r"<w:r(?:\s[^>]*)?>\s*(<w:rPr>.*?</w:rPr>)", re.DOTALL)
CONTACT_LINE_RE = re.compile(r"^\s*(e-?mail|е-?mail|orcid)\b", re.IGNORECASE)
LANG_VALUE_RE = re.compile(r'(<w:lang\b[^>]*?\bw:val=")[^"]*(")')
LOCALES = {"uk": "uk-UA", "en": "en-US"}

# A date value: either the placeholder (in Cyrillic or Latin X) or a real date.
PLACEHOLDER_RE = re.compile(r"^[ХX]{2}\.[ХX]{2}\.(?:[ХX]{4}|\d{4})$")
DATE_VALUE = r"[ХX]{2}\.[ХX]{2}\.(?:[ХX]{4}|\d{4})|\d{1,2}\.\d{1,2}\.\d{4}"
DATE_VALUE_RE = re.compile(DATE_VALUE)

# How far above a © byline the author block's contact lines can sit.
CONTACT_LOOKBACK = 6


def load_dates(config_path="config.yml"):
    """(values, overwrite_existing) from config.yml, with safe defaults."""
    try:
        with open(config_path, encoding="utf-8") as handle:
            config = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        config = {}
    section = config.get(CONFIG_SECTION) or {}
    values = tuple(str(section.get(field) or PLACEHOLDER) for field in FIELDS)
    return values, bool(section.get("overwrite_existing", False))


def _text(fragment):
    return "".join(TEXT_NODE_RE.findall(fragment)).strip()


def _language(text):
    return "uk" if CYRILLIC_RE.search(text) else "en"


def _escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def found_dates(text):
    """[(label_index, label, value)] for the date labels present in `text`.

    The three lines are separated by ``<w:br/>``, which carries no text, so the
    labels arrive run together ("Received: ХХ.ХХ.ХХХХAccepted: ..."); each one
    is located by its own label rather than by splitting the line.
    """
    for language, labels in LABELS.items():
        hits = []
        for index, label in enumerate(labels):
            match = re.search(rf"{label}\s*:\s*({DATE_VALUE})", text)
            if match:
                hits.append((match.start(), index, label, match.group(1)))
        if hits:
            hits.sort()
            return language, [(index, label, value) for _, index, label, value in hits]
    return None, []


def date_block_xml(model_fragment, language, lines):
    """A date paragraph wearing `model_fragment`'s own formatting.

    `lines` is [(label, value)], one per rendered line.
    """
    paragraph_props = PARAGRAPH_PROPS_RE.search(model_fragment)
    run_props = RUN_PROPS_RE.search(model_fragment)
    paragraph_props = paragraph_props.group(0) if paragraph_props else ""
    run_props = run_props.group(1) if run_props else ""

    # The model's spell-check locale is whatever the author last typed in;
    # carrying "en-US" onto the Ukrainian lines would underline every word.
    run_props = LANG_VALUE_RE.sub(rf"\g<1>{LOCALES[language]}\g<2>", run_props)

    runs = []
    for index, (label, value) in enumerate(lines):
        # Lines two and three are separated by a break, not by a new paragraph,
        # which is how the complete articles are written.
        line_break = "<w:br/>" if index else ""
        text = _escape(f"{label}: {value}")
        runs.append(f"<w:r>{run_props}{line_break}<w:t>{text}</w:t></w:r>")
    return f"<w:p>{paragraph_props}{''.join(runs)}</w:p>"


def _paragraphs(xml):
    return [
        (match.start(), match.end(), match.group(0), _text(match.group(0)))
        for match in PARAGRAPH_RE.finditer(xml)
    ]


def plan_insertions(paragraphs, dates):
    """[(start, end, xml, language)] for every author block missing its dates."""
    edits = []
    for index, (_, _, _, text) in enumerate(paragraphs):
        if not text or not starts_with_copyright(text):
            continue
        # The CC-BY notice is a © paragraph too, and a Latin one, so without
        # this it reads as a third (English) byline and the block lands in the
        # middle of the Ukrainian author block.
        if LICENSE_NOTICE_RE.search(text):
            continue
        language = _language(text)

        # The contact lines directly above the byline; the last one is where
        # the dates belong.
        anchor = None
        seen = 0
        for candidate in range(index - 1, -1, -1):
            candidate_text = paragraphs[candidate][3]
            if not candidate_text:
                continue
            seen += 1
            if seen > CONTACT_LOOKBACK:
                break
            if CONTACT_LINE_RE.match(candidate_text):
                anchor = candidate
                break
        if anchor is None:
            continue

        already_there = any(
            found_dates(paragraphs[between][3])[0] == language
            for between in range(anchor + 1, index)
        )
        if already_there:
            continue

        end = paragraphs[anchor][1]
        lines = list(zip(LABELS[language], dates))
        edits.append((end, end, date_block_xml(paragraphs[anchor][2], language, lines), language))
    return edits


def plan_updates(paragraphs, dates, overwrite_existing):
    """[(start, end, xml, language)] for date paragraphs whose values change."""
    edits = []
    for start, end, fragment, text in paragraphs:
        if not text:
            continue
        language, hits = found_dates(text)
        if not hits:
            continue

        lines, changed = [], False
        for field_index, label, current in hits:
            wanted = dates[field_index]
            # A placeholder means "not decided yet", so it never overwrites
            # what is already there — including a half-filled "ХХ.ХХ.2026",
            # whose year would otherwise be thrown away.
            if PLACEHOLDER_RE.match(wanted):
                keep = True
            else:
                # A date an editor actually filled in outranks the issue value.
                keep = not overwrite_existing and not PLACEHOLDER_RE.match(current)
            value = current if keep else wanted
            changed = changed or value != current
            lines.append((label, value))
        if changed:
            edits.append((start, end, date_block_xml(fragment, language, lines), language))
    return edits


def apply_dates(source_path, target_path, dates, overwrite_existing=False, dry_run=False):
    """Write `source_path` to `target_path` with the dates inserted/filled in.

    Returns (inserted_blocks, updated_blocks).
    """
    with zipfile.ZipFile(source_path) as archive:
        entries = [(item, archive.read(item.filename)) for item in archive.infolist()]

    document = next(
        (payload for item, payload in entries if item.filename == "word/document.xml"),
        None,
    )
    if document is None:
        if not dry_run and source_path != target_path:
            shutil.copy2(source_path, target_path)
        return 0, 0

    xml = document.decode("utf-8")
    paragraphs = _paragraphs(xml)
    insertions = plan_insertions(paragraphs, dates)
    updates = plan_updates(paragraphs, dates, overwrite_existing)

    if not insertions and not updates:
        # Nothing to do: copy the file itself, so it stays bit-identical.
        if not dry_run and source_path != target_path:
            shutil.copy2(source_path, target_path)
        return 0, 0

    if not dry_run:
        updated = xml
        for start, end, fragment, _ in sorted(insertions + updates, reverse=True):
            updated = updated[:start] + fragment + updated[end:]
        payload = updated.encode("utf-8")

        temporary = f"{target_path}.tmp"
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for item, data in entries:
                archive.writestr(
                    item, payload if item.filename == "word/document.xml" else data
                )
        os.replace(temporary, target_path)

    return len(insertions), len(updates)


def _backup(input_folder, filenames):
    """Copy `filenames` to a fresh directory, never into an existing one.

    Reusing a directory is how a backup gets destroyed: run the tool twice and
    the second run would overwrite the pristine originals with the copies it
    has already edited.
    """
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = f"articles_backup_{stamp}"
    suffix = 2
    while os.path.exists(folder):
        folder = f"articles_backup_{stamp}-{suffix}"
        suffix += 1
    os.makedirs(folder)
    for filename in filenames:
        shutil.copy2(os.path.join(input_folder, filename), os.path.join(folder, filename))
    return folder


def process_folder(
    input_folder,
    output_folder,
    dates,
    overwrite_existing=False,
    dry_run=False,
    backup=True,
):
    in_place = os.path.abspath(input_folder) == os.path.abspath(output_folder)
    filenames = sorted(
        f for f in os.listdir(input_folder) if f.endswith(".docx") and not f.startswith("~$")
    )

    print(f"Dates: received={dates[0]} accepted={dates[1]} published={dates[2]}")
    print(f"Existing dates are {'overwritten' if overwrite_existing else 'kept'}.")

    # Work out what would change before touching anything, so the backup covers
    # exactly the files at risk and a run that changes nothing writes nothing.
    plan = {}
    for filename in filenames:
        source = os.path.join(input_folder, filename)
        added, changed = apply_dates(source, source, dates, overwrite_existing, dry_run=True)
        if added or changed:
            plan[filename] = (added, changed)

    if dry_run:
        print("DRY RUN — nothing is written.\n")
    elif not plan:
        print("\nNothing to change; no files written.")
        return 0
    else:
        if in_place and backup:
            print(f"Backup of the {len(plan)} file(s) about to change: "
                  f"{_backup(input_folder, sorted(plan))}")
        os.makedirs(output_folder, exist_ok=True)
        print(f"Writing to {'the input folder (in place)' if in_place else output_folder}\n")

    inserted = updated = 0
    for filename in filenames:
        if dry_run:
            added, changed = plan.get(filename, (0, 0))
        else:
            added, changed = apply_dates(
                os.path.join(input_folder, filename),
                os.path.join(output_folder, filename),
                dates,
                overwrite_existing,
            )
        inserted += added
        updated += changed
        if added or changed:
            parts = []
            if added:
                parts.append(f"inserted {added} block(s)")
            if changed:
                parts.append(f"filled in {changed} block(s)")
            print(f"  {filename}: {', '.join(parts)}")

    verb = "would change" if dry_run else "changed"
    print(
        f"\n{len(filenames)} article(s): {len(plan)} {verb} "
        f"({inserted} block(s) inserted, {updated} filled in), "
        f"{len(filenames) - len(plan)} left untouched."
    )
    return len(plan)


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input_folder", nargs="?", help="Folder of DOCX articles.")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help="Output folder.")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Edit the articles in the input folder instead of writing copies.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip the timestamped backup that --in-place takes first.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing anything.",
    )
    parser.add_argument(
        "--overwrite-existing",
        action="store_true",
        help="Replace dates that are already filled in, not just the placeholders.",
    )
    for field in FIELDS:
        parser.add_argument(f"--{field}", help=f"Override submission_dates.{field}.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    folder = args.input_folder
    if not folder:
        config = yaml.safe_load(open("config.yml", encoding="utf-8")) or {}
        folder = config.get("app", {}).get("input_folder") or "articles"

    dates, overwrite_existing = load_dates()
    dates = tuple(
        getattr(args, field) or value for field, value in zip(FIELDS, dates)
    )
    overwrite_existing = overwrite_existing or args.overwrite_existing

    process_folder(
        folder,
        folder if args.in_place else args.output,
        dates,
        overwrite_existing=overwrite_existing,
        dry_run=args.dry_run,
        backup=not args.no_backup,
    )
