import xml.etree.ElementTree as ET

def create_literature_xml(literature_references):
    """Converts the extracted literature references into an XML format."""
    root = ET.Element("citation_list")
    for i, reference in enumerate(literature_references, start=1):
        citation = ET.SubElement(root, "citation", key=f"ref{i}")
        unstructured_citation = ET.SubElement(citation, "unstructured_citation")
        unstructured_citation.text = reference
    xml_str = ET.tostring(root, encoding="unicode")
    return xml_str
