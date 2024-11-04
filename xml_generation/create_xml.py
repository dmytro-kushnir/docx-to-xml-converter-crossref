import xml.etree.ElementTree as ET
from datetime import datetime
import lxml.etree as etree
from xml_generation.create_authors import create_xml_for_authors
from xml_generation.create_literature import create_literature_xml
from xml_generation.create_pages import create_pages_xml

def create_journal_metadata():
    """Creates the common journal metadata part of the XML."""
    journal_metadata = ET.Element("journal_metadata")
    ET.SubElement(journal_metadata, "full_title").text = "Computer systems and network"
    ET.SubElement(journal_metadata, "abbrev_title").text = "CSN"
    ET.SubElement(journal_metadata, "issn", media_type="print").text = "27072371"
    ET.SubElement(journal_metadata, "issn", media_type="electronic").text = "27072371"

    doi_data = ET.SubElement(journal_metadata, "doi_data")
    ET.SubElement(doi_data, "doi").text = "10.23939/csn"
    ET.SubElement(doi_data, "resource").text = "http://science.lpnu.ua/csn"

    return journal_metadata

def create_journal_issue():
    """Creates the journal issue metadata part of the XML."""
    journal_issue = ET.Element("journal_issue")

    publication_date = ET.SubElement(journal_issue, "publication_date", media_type="print")
    ET.SubElement(publication_date, "month").text = "06"
    ET.SubElement(publication_date, "year").text = "2024"

    journal_volume = ET.SubElement(journal_issue, "journal_volume")
    ET.SubElement(journal_volume, "volume").text = "6"

    ET.SubElement(journal_issue, "issue").text = "1"

    doi_data = ET.SubElement(journal_issue, "doi_data")
    ET.SubElement(doi_data, "doi").text = "10.23939/csn2024.01"
    ET.SubElement(doi_data, "resource").text = "https://science.lpnu.ua/csn/all-volumes-and-issues/volume-6-number-1-2024"

    return journal_issue

def create_journal_article(title, original_language_title, authors, pages, literature, doi, abstract_text):
    """Creates a journal article element with given details."""
    NSMAP = {
        "jats": "http://www.ncbi.nlm.nih.gov/JATS1",
        "xml": "http://www.w3.org/XML/1998/namespace"
    }
    journal_article = etree.Element("journal_article", publication_type="full_text", nsmap=NSMAP)

    # Titles section
    titles = etree.SubElement(journal_article, "titles")
    etree.SubElement(titles, "title").text = title
    if original_language_title:
        etree.SubElement(titles, "original_language_title").text = original_language_title

    # Contributors section
    contributors_xml = create_xml_for_authors(authors)
    contributors_element = etree.fromstring(contributors_xml)
    contributors_element.tag = "contributors"
    journal_article.append(contributors_element)

    # Abstract section
    abstract = etree.SubElement(journal_article, "{http://www.ncbi.nlm.nih.gov/JATS1}abstract")
    abstract.set("{http://www.w3.org/XML/1998/namespace}lang", "en")
    etree.SubElement(abstract, "{http://www.ncbi.nlm.nih.gov/JATS1}p").text = abstract_text if abstract_text else "Abstract not available."

    # Publication Date section
    publication_date = etree.SubElement(journal_article, "publication_date", media_type="print")
    etree.SubElement(publication_date, "month").text = "06"
    etree.SubElement(publication_date, "year").text = "2024"

    # Pages section
    pages_xml = create_pages_xml(pages[0], pages[1])
    pages_element = etree.fromstring(pages_xml)
    journal_article.append(pages_element)

    # DOI data section
    doi_data = etree.SubElement(journal_article, "doi_data")
    etree.SubElement(doi_data, "doi").text = doi
    etree.SubElement(doi_data, "resource").text = "https://example.com/article"  # Replace with real link

    # Literature references section
    literature_xml = create_literature_xml(literature)
    literature_element = etree.fromstring(literature_xml)
    journal_article.append(literature_element)

    return journal_article

def create_full_xml(articles_data):
    root = etree.Element("doi_batch", version="4.4.2", xmlns="http://www.crossref.org/schema/4.4.2")

    # Create head
    head = etree.SubElement(root, "head")
    current_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    etree.SubElement(head, "doi_batch_id").text = f"register_issue_{current_timestamp}"
    etree.SubElement(head, "timestamp").text = current_timestamp

    depositor = etree.SubElement(head, "depositor")
    etree.SubElement(depositor, "depositor_name").text = "depositor:depositor"
    etree.SubElement(depositor, "email_address").text = "mail.com"
    etree.SubElement(head, "registrant").text = "registrant"

    # Create body
    body = etree.SubElement(root, "body")
    journal = etree.SubElement(body, "journal")

    # Add journal metadata
    journal_metadata = create_journal_metadata()
    journal.append(etree.fromstring(ET.tostring(journal_metadata)))

    # Add journal issue
    journal_issue = create_journal_issue()
    journal.append(etree.fromstring(ET.tostring(journal_issue)))

    # Add articles
    for article in articles_data:
        title, original_language_title, authors, pages, literature, doi, abstract_text = article
        journal_article = create_journal_article(title, original_language_title, authors, pages, literature, doi, abstract_text)
        journal.append(etree.fromstring(ET.tostring(journal_article)))

    # Convert to a pretty-printed XML string using lxml
    pretty_xml_str = etree.tostring(root, pretty_print=True, encoding='unicode')
    return pretty_xml_str
