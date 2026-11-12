import re
import xml.etree.ElementTree as ET

# The reference's own list number ("1. ", "12) ", "[3] "), kept by the source
# when the list was typed by hand rather than auto-numbered. Crossref asks for
# unstructured citations without it, and its parser splits such entries — a
# numbered GDPR reference was once matched to an unrelated chemistry article.
# One to three digits only, so a leading year ("2016. …") is left alone.
LIST_NUMBER_RE = re.compile(r"^\s*(?:\[\d{1,3}\]|\d{1,3}[.)])\s+")


def strip_list_number(reference):
    return LIST_NUMBER_RE.sub("", reference, count=1)


def create_literature_xml(literature_references):
    """Converts the extracted literature references into an XML format."""
    root = ET.Element("citation_list")
    for i, reference in enumerate(literature_references, start=1):
        citation = ET.SubElement(root, "citation", key=f"ref{i}")
        unstructured_citation = ET.SubElement(citation, "unstructured_citation")
        unstructured_citation.text = strip_list_number(reference)
    xml_str = ET.tostring(root, encoding="unicode")
    return xml_str
