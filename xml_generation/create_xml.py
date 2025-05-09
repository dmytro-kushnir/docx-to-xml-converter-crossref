import xml.etree.ElementTree as ET
from datetime import datetime
import lxml.etree as etree
import yaml
from xml_generation.create_authors import create_xml_for_authors
from xml_generation.create_literature import create_literature_xml
from xml_generation.create_pages import create_pages_xml
from xml_generation.slug_utils import slugify_title

# Load configuration from YAML file
with open("config.yml", "r") as config_file:
    config = yaml.safe_load(config_file)

PUBLICATION_YEAR = config["publication"]["year"]
PUBLICATION_MONTH = config["publication"]["month"]
JOURNAL_VOLUME = config["publication"]["volume"]
JOURNAL_ISSUE = config["publication"]["issue"]
JOURNAL_DOI = config["journal"]["doi"]
JOURNAL_URL = config["journal"]["base_url"]
ISSN_PRINT = config["journal"]["issn"]["print"]
ISSN_ELECTRONIC = config["journal"]["issn"]["electronic"]
JOURNAL_FULL_TITLE = config["journal"]["full_title"]
JOURNAL_ABBREV_TITLE = config["journal"]["abbrev_title"]
DEPOSITOR_NAME = config["depositor"]["name"]
DEPOSITOR_EMAIL = config["depositor"]["email"]
REGISTRANT = config["registrant"]

def generate_doi(start_page):
    """Generate a DOI string based on the configuration and start page."""
    return f"{JOURNAL_DOI}{PUBLICATION_YEAR}.{int(JOURNAL_ISSUE):02d}.{start_page:03d}"

def create_journal_metadata():
    """Creates the common journal metadata part of the XML."""
    journal_metadata = ET.Element("journal_metadata")
    ET.SubElement(journal_metadata, "full_title").text = JOURNAL_FULL_TITLE
    ET.SubElement(journal_metadata, "abbrev_title").text = JOURNAL_ABBREV_TITLE
    ET.SubElement(journal_metadata, "issn", media_type="print").text = ISSN_PRINT
    ET.SubElement(journal_metadata, "issn", media_type="electronic").text = ISSN_ELECTRONIC

    doi_data = ET.SubElement(journal_metadata, "doi_data")
    ET.SubElement(doi_data, "doi").text = JOURNAL_DOI
    ET.SubElement(doi_data, "resource").text = JOURNAL_URL

    return journal_metadata

def create_journal_issue():
    """Creates the journal issue metadata part of the XML."""
    journal_issue = ET.Element("journal_issue")

    publication_date = ET.SubElement(journal_issue, "publication_date", media_type="print")
    ET.SubElement(publication_date, "month").text = PUBLICATION_MONTH
    ET.SubElement(publication_date, "year").text = PUBLICATION_YEAR

    journal_volume = ET.SubElement(journal_issue, "journal_volume")
    ET.SubElement(journal_volume, "volume").text = JOURNAL_VOLUME

    ET.SubElement(journal_issue, "issue").text = JOURNAL_ISSUE

    doi_data = ET.SubElement(journal_issue, "doi_data")
    ET.SubElement(doi_data, "doi").text = f"{JOURNAL_DOI}{PUBLICATION_YEAR}.0{JOURNAL_ISSUE}"
    ET.SubElement(doi_data, "resource").text = f"{JOURNAL_URL}/all-volumes-and-issues/volume-{JOURNAL_VOLUME}-number-{JOURNAL_ISSUE}-{PUBLICATION_YEAR}"

    return journal_issue

def create_journal_article(title, original_language_title, authors, pages, literature, abstract_text):
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
    etree.SubElement(publication_date, "month").text = PUBLICATION_MONTH
    etree.SubElement(publication_date, "year").text = PUBLICATION_YEAR

    # Pages section
    pages_xml = create_pages_xml(pages[0], pages[1])
    pages_element = etree.fromstring(pages_xml)
    journal_article.append(pages_element)

    # DOI data section
    doi_data = etree.SubElement(journal_article, "doi_data")
    etree.SubElement(doi_data, "doi").text = generate_doi(pages[0])

    # Generate the resource URL dynamically
    formatted_title = slugify_title(title)
    resource_url = f"{JOURNAL_URL}/all-volumes-and-issues/volume-{JOURNAL_VOLUME}-number-{JOURNAL_ISSUE}-{PUBLICATION_YEAR}/{formatted_title}"
    etree.SubElement(doi_data, "resource").text = resource_url

    # Literature references section
    literature_xml = create_literature_xml(literature)
    literature_element = etree.fromstring(literature_xml)
    journal_article.append(literature_element)

    return journal_article

def create_full_xml(articles_data):
    root = etree.Element(
        "doi_batch",
        attrib={
            "version": "4.4.2",
            "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation": "http://www.crossref.org/schema/4.4.2 http://www.crossref.org/schema/deposit/crossref4.4.2.xsd"
        },
        nsmap={
            None: "http://www.crossref.org/schema/4.4.2",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "jats": "http://www.ncbi.nlm.nih.gov/JATS1"
        }
    )

    # Create head
    head = etree.SubElement(root, "head")
    current_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    etree.SubElement(head, "doi_batch_id").text = f"register_issue_{current_timestamp}"
    etree.SubElement(head, "timestamp").text = current_timestamp

    depositor = etree.SubElement(head, "depositor")
    etree.SubElement(depositor, "depositor_name").text = DEPOSITOR_NAME
    etree.SubElement(depositor, "email_address").text = DEPOSITOR_EMAIL
    etree.SubElement(head, "registrant").text = REGISTRANT

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
        title, original_language_title, authors, pages, literature, abstract_text = article
        journal_article = create_journal_article(title, original_language_title, authors, pages, literature, abstract_text)
        journal.append(etree.fromstring(ET.tostring(journal_article)))


    # Convert to a pretty-printed XML string using lxml
    xml_str = etree.tostring(root, pretty_print=True, encoding='unicode')

    # Prepend the XML declaration
    xml_with_declaration = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'

    return xml_with_declaration
