import re
import xml.etree.ElementTree as ET


def create_xml_for_authors(authors_text):
    """Converts extracted authors into XML format."""
    authors_list = [author.strip() for author in authors_text.split(",")]
    root = ET.Element("contributors")
    for author in authors_list:
        # Split into surname and given name (e.g., "Glukhov V.S.")
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

        person_name = ET.SubElement(root, "person_name", sequence="additional", contributor_role="author")
        ET.SubElement(person_name, "given_name").text = given_name.strip()
        ET.SubElement(person_name, "surname").text = surname.strip()

    # Convert to XML string (for display purposes)
    xml_str = ET.tostring(root, encoding="unicode")
    return xml_str

