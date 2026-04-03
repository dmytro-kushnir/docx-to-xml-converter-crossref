import re
import xml.etree.ElementTree as ET


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
            emitted += 1

    return ET.tostring(root, encoding="unicode")


def create_xml_organizations_then_authors(organization_lines, authors_text):
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

    persons_xml = create_xml_for_authors(authors_text)
    persons_root = ET.fromstring(persons_xml)
    for child in list(persons_root):
        child.set("sequence", next_seq())
        root.append(child)

    return ET.tostring(root, encoding="unicode")


def create_xml_for_authors(authors_text):
    """Converts extracted authors into XML format."""
    authors_list = [author.strip() for author in authors_text.split(",")]
    root = ET.Element("contributors")
    emitted = 0

    for author in authors_list:
        # Split into surname and given name (e.g., "Maksymovych M.")
        name_parts = re.split(r'\s+', author)
        if len(name_parts) < 2:
            # Skip if the author does not have both surname and given name
            continue

        surname = name_parts[0]
        given_name = ' '.join(name_parts[1:])

        # Check for empty names and skip if found
        if not given_name or not surname:
            continue

        # Remove any numbers accidentally included in given_name
        given_name = re.sub(r'\d+', '', given_name)

        sequence = "first" if emitted == 0 else "additional"
        emitted += 1

        person_name = ET.SubElement(root, "person_name", sequence=sequence, contributor_role="author")
        ET.SubElement(person_name, "given_name").text = given_name.strip()
        ET.SubElement(person_name, "surname").text = surname.strip()

    # Convert to XML string (for display purposes)
    xml_str = ET.tostring(root, encoding="unicode")
    return xml_str
