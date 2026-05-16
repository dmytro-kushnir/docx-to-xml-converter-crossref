import xml.etree.ElementTree as ET
from datetime import datetime
import lxml.etree as etree
import yaml
from docx_processing.extractors import (
    affiliation_department_for_crossref,
    affiliation_lines_for_crossref_organization,
)
from xml_generation.crossref.create_authors import (
    create_xml_for_authors,
    create_xml_for_authors_with_affiliations,
)
from xml_generation.crossref.institution_ror import resolve_institution
from xml_generation.crossref.create_literature import create_literature_xml
from xml_generation.crossref.create_pages import create_pages_xml
from xml_generation.crossref.slug_utils import slugify_title

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
AI_NS = "http://www.crossref.org/AccessIndicators.xsd"
LICENSE_URL = config.get("license", {}).get(
    "url", "https://creativecommons.org/licenses/by/4.0/"
)
LICENSE_APPLIES_TO = config.get("license", {}).get("applies_to", "vor")
CROSSREF_SCHEMA_VERSION = config.get("crossref", {}).get("schema_version", "5.4.0")
CROSSREF_NS = f"http://www.crossref.org/schema/{CROSSREF_SCHEMA_VERSION}"
INSTITUTIONS_CONFIG = config.get("institutions") or {}
DEFAULT_INSTITUTION_ID = config.get("crossref", {}).get("default_institution")


def _qualify_crossref_ns(element, ns=CROSSREF_NS):
    """Ensure elements parsed from stdlib ElementTree use the Crossref default namespace."""
    if element.tag and not str(element.tag).startswith("{"):
        element.tag = f"{{{ns}}}{element.tag}"
    for child in element:
        _qualify_crossref_ns(child, ns)


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

def create_journal_article(
    title,
    original_language_title,
    authors,
    pages,
    literature,
    abstract_text,
    affiliation_lines,
    author_orcids=None,
):
    """Creates a journal article element with given details.

    affiliation_lines: primary university/institute → ROR <affiliations> on each <person_name>.
    author_orcids: list of https://orcid.org/... URLs, matched to authors in order.
    """
    NSMAP = {
        None: CROSSREF_NS,
        "jats": "http://www.ncbi.nlm.nih.gov/JATS1",
        "xml": "http://www.w3.org/XML/1998/namespace",
        "ai": AI_NS,
    }
    journal_article = etree.Element("journal_article", publication_type="full_text", nsmap=NSMAP)

    # Titles section
    titles = etree.SubElement(journal_article, "titles")
    etree.SubElement(titles, "title").text = title
    if original_language_title:
        etree.SubElement(titles, "original_language_title").text = original_language_title

    # Contributors: person_name + ROR affiliations (schema 5.4.0)
    org_lines = affiliation_lines_for_crossref_organization(affiliation_lines or [])
    institution = None
    if org_lines:
        institution = resolve_institution(
            org_lines[0],
            INSTITUTIONS_CONFIG,
            default_institution_id=DEFAULT_INSTITUTION_ID,
        )
    department = affiliation_department_for_crossref(affiliation_lines or [])
    contributors_xml = create_xml_for_authors_with_affiliations(
        authors,
        institution=institution,
        author_orcids=author_orcids,
        department=department,
    )
    if len(ET.fromstring(contributors_xml)) == 0:
        contributors_xml = create_xml_for_authors(authors, author_orcids=author_orcids)
    contributors_element = etree.fromstring(contributors_xml)
    _qualify_crossref_ns(contributors_element)
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
    _qualify_crossref_ns(pages_element)
    journal_article.append(pages_element)

    # License (AccessIndicators) — before doi_data
    access_program = etree.SubElement(
        journal_article, f"{{{AI_NS}}}program", name="AccessIndicators"
    )
    license_ref = etree.SubElement(
        access_program,
        f"{{{AI_NS}}}license_ref",
        applies_to=LICENSE_APPLIES_TO,
    )
    license_ref.text = LICENSE_URL

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
    _qualify_crossref_ns(literature_element)
    journal_article.append(literature_element)

    return journal_article

def create_full_xml(articles_data):
    schema_xsd = f"http://www.crossref.org/schemas/crossref{CROSSREF_SCHEMA_VERSION}.xsd"
    root = etree.Element(
        "doi_batch",
        attrib={
            "version": CROSSREF_SCHEMA_VERSION,
            "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation": (
                f"{CROSSREF_NS} {schema_xsd}"
            ),
        },
        nsmap={
            None: CROSSREF_NS,
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "jats": "http://www.ncbi.nlm.nih.gov/JATS1",
            "ai": AI_NS,
        },
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
    jmeta = etree.fromstring(ET.tostring(journal_metadata))
    _qualify_crossref_ns(jmeta)
    journal.append(jmeta)

    # Add journal issue
    journal_issue = create_journal_issue()
    jissue = etree.fromstring(ET.tostring(journal_issue))
    _qualify_crossref_ns(jissue)
    journal.append(jissue)

    # Add articles
    for article in articles_data:
        (
            title,
            original_language_title,
            authors,
            pages,
            literature,
            abstract_text,
            affiliation_lines,
        ) = article[:7]
        author_orcids = article[7] if len(article) > 7 else None
        journal_article = create_journal_article(
            title,
            original_language_title,
            authors,
            pages,
            literature,
            abstract_text,
            affiliation_lines,
            author_orcids=author_orcids,
        )
        ja = etree.fromstring(ET.tostring(journal_article))
        _qualify_crossref_ns(ja)
        journal.append(ja)


    # Convert to a pretty-printed XML string using lxml
    xml_str = etree.tostring(root, pretty_print=True, encoding='unicode')

    # Prepend the XML declaration
    xml_with_declaration = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'

    return xml_with_declaration
