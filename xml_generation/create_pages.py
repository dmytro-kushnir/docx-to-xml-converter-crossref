import xml.etree.ElementTree as ET

def create_pages_xml(start_page, end_page):
    """Converts the start and end page numbers into an XML format."""
    root = ET.Element("pages")
    ET.SubElement(root, "first_page").text = str(start_page)
    ET.SubElement(root, "last_page").text = str(end_page)

    # Convert to XML string (for display purposes)
    xml_str = ET.tostring(root, encoding="unicode")
    return xml_str
