import re
import xml.etree.ElementTree as ET


def create_xml_for_authors(authors_text):
    """Converts extracted authors into XML format."""
    authors_list = [author.strip() for author in authors_text.split(",")]
    root = ET.Element("contributors")

    for index, author in enumerate(authors_list):
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

        # Set the sequence attribute for the first author
        sequence = "first" if index == 0 else "additional"

        person_name = ET.SubElement(root, "person_name", sequence=sequence, contributor_role="author")
        ET.SubElement(person_name, "given_name").text = given_name.strip()
        ET.SubElement(person_name, "surname").text = surname.strip()

    # Convert to XML string (for display purposes)
    xml_str = ET.tostring(root, encoding="unicode")
    return xml_str

