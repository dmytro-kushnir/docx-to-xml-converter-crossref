import re
import xml.etree.ElementTree as ET
from docx_processing.extractors import split_copyright_authors


def create_contributors_xml_from_override(items):
    """Build <contributors> with mixed <organization> and <person_name> from YAML override list."""
    root = ET.Element("contributors")
    if not items:
        return ET.tostring(root, encoding="unicode")

    emitted = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        explicit = item.get("sequence")
        if explicit in ("first", "additional"):
            seq = explicit
        else:
            seq = "first" if emitted == 0 else "additional"
        kind = (item.get("type") or item.get("kind") or "").lower()
        if kind == "organization":
            text = (item.get("text") or "").strip()
            if not text:
                continue
            org = ET.SubElement(
                root, "organization", sequence=seq, contributor_role="author"
            )
            org.text = text
            emitted += 1
        elif kind == "person":
            given = (item.get("given_name") or "").strip()
            surname = (item.get("surname") or "").strip()
            if not surname:
                continue
            person_name = ET.SubElement(
                root, "person_name", sequence=seq, contributor_role="author"
            )
            ET.SubElement(person_name, "given_name").text = given
            ET.SubElement(person_name, "surname").text = surname
            orcid = (item.get("orcid") or "").strip()
            if orcid:
                ET.SubElement(person_name, "ORCID").text = orcid
            emitted += 1

    return ET.tostring(root, encoding="unicode")


def _attach_orcid(person_name, author_orcids, author_index):
    if author_orcids and author_index < len(author_orcids) and author_orcids[author_index]:
        ET.SubElement(person_name, "ORCID").text = author_orcids[author_index]


def create_xml_organizations_then_authors(organization_lines, authors_text, author_orcids=None):
    """Emit <organization> nodes from extracted lines, then <person_name> from authors_text; re-sequence in order."""
    root = ET.Element("contributors")
    n = 0

    def next_seq():
        nonlocal n
        seq = "first" if n == 0 else "additional"
        n += 1
        return seq

    for org_text in organization_lines:
        text = (org_text or "").strip()
        if not text:
            continue
        org = ET.SubElement(
            root, "organization", sequence=next_seq(), contributor_role="author"
        )
        org.text = text

    persons_xml = create_xml_for_authors(authors_text, author_orcids=author_orcids)
    persons_root = ET.fromstring(persons_xml)
    for child in list(persons_root):
        child.set("sequence", next_seq())
        root.append(child)

    return ET.tostring(root, encoding="unicode")


def _parse_author_name(author_str):
    """Parse one copyright-line author into (given_name, surname), or None."""
    t = author_str.strip()
    if not t:
        return None

    # I. V. Tyshko / I.V. Teleshko
    m = re.match(
        r"^([A-Za-zА-ЯІЇЄҐа-яіїєґ]\.){1,4}\s*([A-Za-zА-ЯІЇЄҐа-яіїєґ'\-]{2,})$",
        t,
    )
    if m:
        return " ".join(re.findall(r"[A-Za-zА-ЯІЇЄҐа-яіїєґ]", m.group(1))), m.group(2)

    # Tyshyk I. Y. / Arseniuk V.
    m = re.match(
        r"^([A-Za-zА-ЯІЇЄҐа-яіїєґ'\-]{2,})\s+((?:[A-Za-zА-ЯІЇЄҐа-яіїєґ]\.\s*){1,4})$",
        t,
    )
    if m:
        initials = re.findall(r"[A-Za-zА-ЯІЇЄҐа-яіїєґ]", m.group(2))
        return " ".join(initials), m.group(1)

    # Ivan Tyshyk (full first + surname)
    m = re.match(
        r"^([A-Z][a-zА-ЯІЇЄҐа-яіїєґ'\-]+)\s+([A-Z][A-Za-zА-ЯІЇЄҐа-яіїєґ'\-]{1,})$",
        t,
    )
    if m:
        return m.group(1), m.group(2)

    # Fallback: first token surname, rest given (legacy)
    name_parts = re.split(r"\s+", t)
    if len(name_parts) >= 2:
        return " ".join(name_parts[1:]), name_parts[0]
    return None


def create_xml_for_authors(authors_text, author_orcids=None):
    """Converts extracted authors into XML format."""
    authors_list = split_copyright_authors(authors_text)
    root = ET.Element("contributors")
    emitted = 0
    author_orcids = author_orcids or []

    for author_index, author in enumerate(authors_list):
        parsed = _parse_author_name(author)
        if not parsed:
            continue

        given_name, surname = parsed
        given_name = re.sub(r"\d+", "", given_name).strip()
        surname = surname.strip()
        if not given_name or not surname:
            continue

        sequence = "first" if emitted == 0 else "additional"
        emitted += 1

        person_name = ET.SubElement(root, "person_name", sequence=sequence, contributor_role="author")
        ET.SubElement(person_name, "given_name").text = given_name
        ET.SubElement(person_name, "surname").text = surname
        _attach_orcid(person_name, author_orcids, author_index)

    xml_str = ET.tostring(root, encoding="unicode")
    return xml_str
