import copy
import os
import re

import lxml.etree as etree
from docx import Document
from docx.oxml.ns import qn

def parse_xml(xml_path):
    """Parse XML file and return its root element."""
    tree = etree.parse(xml_path)
    return tree.getroot()


def _crossref_namespace(root):
    if root.tag.startswith("{"):
        return root.tag[1 : root.tag.index("}")]
    return root.nsmap.get(None) or "http://www.crossref.org/schema/5.4.0"


def _nsmap(root):
    return {"ns": _crossref_namespace(root)}

def _contributors_display_string(article, nsmap):
    """Author names for tables — person_name only; omit <organization> (affiliations)."""
    contributors_el = article.find("ns:contributors", namespaces=nsmap)
    if contributors_el is None:
        return "N/A"
    parts = []
    for child in list(contributors_el):
        tag = etree.QName(child).localname
        if tag != "person_name":
            continue
        gn_el = child.find("ns:given_name", namespaces=nsmap)
        sn_el = child.find("ns:surname", namespaces=nsmap)
        gn = (gn_el.text or "").strip() if gn_el is not None else ""
        sn = (sn_el.text or "").strip() if sn_el is not None else ""
        label = f"{gn} {sn}".strip()
        if label:
            parts.append(label)
    return ", ".join(parts) if parts else "N/A"


def parse_journal_metadata(xml_data, nsmap):
    """Extract journal title, volume, issue, year, ISSN, and URLs from XML."""
    journal_metadata = xml_data.xpath('//ns:journal_metadata', namespaces=nsmap)[0]
    journal_title = journal_metadata.find('ns:full_title', namespaces=nsmap).text

    issn_node = journal_metadata.find('ns:issn[@media_type="print"]', namespaces=nsmap)
    issn = issn_node.text if issn_node is not None else "N/A"

    journal_url_node = journal_metadata.find('ns:doi_data/ns:resource', namespaces=nsmap)
    journal_url = journal_url_node.text if journal_url_node is not None else "N/A"

    issue_metadata = xml_data.xpath('//ns:journal_issue', namespaces=nsmap)[0]
    volume = issue_metadata.find('ns:journal_volume/ns:volume', namespaces=nsmap).text
    issue = issue_metadata.find('ns:issue', namespaces=nsmap).text

    issue_url_node = issue_metadata.find('ns:doi_data/ns:resource', namespaces=nsmap)
    issue_url = issue_url_node.text if issue_url_node is not None else "N/A"

    # Extract the year
    year_node = issue_metadata.find('ns:publication_date/ns:year', namespaces=nsmap)
    year = year_node.text if year_node is not None else "N/A"

    return journal_title, volume, issue, year, issn, journal_url, issue_url

def parse_articles(xml_data, nsmap):
    """Extract articles with their authors, titles, pages, DOIs, and URLs from XML."""
    articles = xml_data.xpath('//ns:journal_article', namespaces=nsmap)
    articles_data = []

    for i, article in enumerate(articles, start=1):
        title_node = article.find('ns:titles/ns:title', namespaces=nsmap)
        title_text = title_node.text if title_node is not None else "N/A"

        original_title_node = article.find('ns:titles/ns:original_language_title', namespaces=nsmap)
        original_language_title = original_title_node.text if original_title_node is not None else "N/A"

        authors = _contributors_display_string(article, nsmap)

        # Extract pages
        pages_node = article.find('ns:pages', namespaces=nsmap)
        first_page = pages_node.find('ns:first_page', namespaces=nsmap).text if pages_node is not None and pages_node.find('ns:first_page', namespaces=nsmap) is not None else "N/A"
        last_page = pages_node.find('ns:last_page', namespaces=nsmap).text if pages_node is not None and pages_node.find('ns:last_page', namespaces=nsmap) is not None else "N/A"
        page_range = f"{first_page}-{last_page}" if first_page != "N/A" and last_page != "N/A" else "N/A"

        # Extract article DOI and URL
        url_node = article.find('ns:doi_data/ns:resource', namespaces=nsmap)
        url_text = url_node.text if url_node is not None else "N/A"

        doi_node = article.find('ns:doi_data/ns:doi', namespaces=nsmap)
        doi_text = doi_node.text if doi_node is not None else "N/A"

        articles_data.append((i, authors, title_text, original_language_title, page_range, url_text, doi_text))

    return articles_data

def create_contents_docx(xml_name, output_path, ukrainian_authors=None):
    """Generate contents_eng.docx or contents_ukr.docx based on available data.

    :param xml_root: Parsed XML root.
    :param output_path: Output path for the DOCX file.
    :param articles_data: List of articles containing author names, titles, etc.
    :param ukrainian_authors: Optional list of Ukrainian authors (same order as articles_data).
    """
    xml_root = parse_xml(xml_name)
    nsmap = _nsmap(xml_root)
    journal_title, volume, issue, year, _, _, _ = parse_journal_metadata(xml_root, nsmap)
    articles_data = parse_articles(xml_root, nsmap)

    doc = Document()
    doc.add_paragraph("ЗМІСТ", style="Title")
    doc.add_paragraph(
        f"наукового журналу”\n"
        f"“{journal_title}”\n"
        f"Вип. {volume}, №{issue}, {year} рік", style="Normal"
    )

    doc.add_paragraph("\n")
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"

    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "№"
    hdr_cells[1].text = "Автори"
    hdr_cells[2].text = "Назви статей"

    for idx, article in enumerate(articles_data):
        row_cells = table.add_row().cells
        row_cells[0].text = str(article[0])
        row_cells[1].text = ukrainian_authors[idx] if ukrainian_authors and ukrainian_authors[idx] else article[1]
        row_cells[2].text = article[3] if ukrainian_authors and ukrainian_authors[idx] else article[2] # use original title if ukr authors are present or normal title otherwise

    doc.save(output_path)
    print(f"Contents document saved to {output_path}")


# The DOI-registration information sheet, in the exact layout the registration
# agency receives every issue. Generated *from* this template rather than built
# from scratch, so fonts, column widths, borders and spacing match it exactly.
DOI_LETTER_TEMPLATE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "templates", "doi_letter_template.docx"
)
ISSUE_LINE_RE = re.compile(r"Випуск\s*\d+.*Volume", re.DOTALL)


def _set_text(container, text):
    """Put `text` into the first text node under `container` and empty the rest.

    Word splits a line into many runs ("Випуск ", "8", ", №", …); writing into
    the existing nodes keeps the formatting of the line exactly as it was.
    """
    nodes = list(container.iter(qn("w:t")))
    if not nodes:
        raise ValueError("template element has no text to replace")
    nodes[0].text = text
    nodes[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    for node in nodes[1:]:
        node.text = ""


def _set_hyperlink(document, cell, url):
    """Point the cell's hyperlink at `url` and show `url` as its text."""
    hyperlink = next(cell._tc.iter(qn("w:hyperlink")), None)
    if hyperlink is None:
        _set_text(cell._tc, url)
        return
    rel_id = hyperlink.get(qn("r:id"))
    document.part.rels[rel_id]._target = url
    _set_text(hyperlink, url)


def _initials(given_name):
    """'D. S.' -> 'D.S.', 'Volodymyr' -> 'V.', 'Yu.' stays 'Yu.'"""
    parts = []
    for token in re.split(r"\s+", given_name.strip()):
        if not token:
            continue
        pieces = []
        for piece in token.split("-"):
            pieces.append(piece if piece.endswith(".") else f"{piece[:1]}.")
        parts.append("-".join(pieces))
    return "".join(parts)


def _letter_authors(article, nsmap):
    """'D.S. Havrylov, O.P. Musienko' — initials first, as in the sheet."""
    contributors = article.find("ns:contributors", namespaces=nsmap)
    names = []
    for person in contributors.findall("ns:person_name", namespaces=nsmap) if contributors is not None else []:
        given = person.findtext("ns:given_name", default="", namespaces=nsmap).strip()
        surname = person.findtext("ns:surname", default="", namespaces=nsmap).strip()
        names.append(f"{_initials(given)} {surname}".strip())
    return ", ".join(names)


def _format_issn(issn):
    digits = re.sub(r"[^0-9Xx]", "", issn or "")
    return f"{digits[:4]}-{digits[4:]}" if len(digits) == 8 else issn


def create_doi_letter_docx(
    xml_name,
    output_path,
    journal_title_uk=None,
    journal_url=None,
    template_path=DOI_LETTER_TEMPLATE,
):
    """Generate the DOI-registration information sheet for the issue.

    :param xml_name: Path to the generated crossref.xml.
    :param journal_title_uk: Ukrainian title as registered; the template's own is
        kept when not given.
    :param journal_url: Journal home page; defaults to the one deposited in crossref.xml.
    """
    xml_root = parse_xml(xml_name)
    nsmap = _nsmap(xml_root)
    journal_title, volume, issue, year, issn, deposited_url, issue_url = parse_journal_metadata(
        xml_root, nsmap
    )
    abbrev = xml_root.xpath("//ns:journal_metadata/ns:abbrev_title", namespaces=nsmap)
    abbrev_title = abbrev[0].text if abbrev else ""
    journal_url = journal_url or deposited_url
    articles = xml_root.xpath("//ns:journal_article", namespaces=nsmap)

    doc = Document(template_path)
    issue_line = f"Випуск {volume}, №{issue}, {year} рік (Volume {volume}, Number {issue}, {year})"

    # Шапка: назви журналу й рядок випуску (у шаблоні він трапляється двічі).
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if ISSUE_LINE_RE.search(text):
            _set_text(paragraph._p, issue_line)
        elif re.fullmatch(r"\(.+\)", text):
            _set_text(paragraph._p, f"({journal_title})")
        elif journal_title_uk and re.fullmatch(r"“[^”]+”", text):
            _set_text(paragraph._p, f"“{journal_title_uk}”")
        elif journal_title_uk and text.startswith("Інформація про"):
            quoted = [r for r in paragraph.runs if r.text.startswith("“")]
            if quoted:
                quoted[-1].text = f"“{journal_title_uk}”"

    # Відомості про журнал: рядок визначається за підписом у першій колонці.
    journal_table, articles_table = doc.tables[0], doc.tables[1]
    for row in journal_table.rows:
        label, value = row.cells[0].text.strip(), row.cells[1]
        if "свідоцтва" in label:
            if journal_title_uk:
                _set_text(value._tc, journal_title_uk)
        elif label.startswith("Скорочена"):
            _set_text(value._tc, abbrev_title)
        elif "англійською" in label and "ISSN" in label:
            _set_text(value._tc, journal_title)
        elif label == "ISSN":
            _set_text(value._tc, _format_issn(issn))
        elif "стартової сторінки" in label:
            _set_hyperlink(doc, value, journal_url)
        elif label.startswith("Рік"):
            _set_text(value._tc, year)
        elif label.startswith("Число"):
            _set_text(value._tc, f"Volume {volume}, Number {issue}")
        elif "змісту" in label:
            _set_hyperlink(doc, value, issue_url)

    # Статті: кожен рядок — копія рядка-прототипу з шаблону.
    table = articles_table._tbl
    data_rows = table.findall(qn("w:tr"))[1:]
    prototype = copy.deepcopy(data_rows[0])
    for row in data_rows:
        table.remove(row)
    for number, article in enumerate(articles, start=1):
        title = article.findtext("ns:titles/ns:title", default="", namespaces=nsmap).strip()
        url = article.findtext("ns:doi_data/ns:resource", default="", namespaces=nsmap).strip()
        first = article.findtext("ns:pages/ns:first_page", default="", namespaces=nsmap).strip()
        last = article.findtext("ns:pages/ns:last_page", default="", namespaces=nsmap).strip()
        pages = f"{first}-{last}" if first and last else first

        row = copy.deepcopy(prototype)
        number_cell, text_cell, pages_cell = row.findall(qn("w:tc"))
        _set_text(number_cell, str(number))
        # Перший вузол — «автори. НАЗВА», останній (після розриву рядка) — URL.
        text_nodes = list(text_cell.iter(qn("w:t")))
        text_nodes[0].text = f"{_letter_authors(article, nsmap)}. {title.upper()}"
        for node in text_nodes[1:-1]:
            node.text = ""
        text_nodes[-1].text = url
        _set_text(pages_cell, pages)
        table.append(row)

    doc.save(output_path)
    print(f"DOI Letter document saved to {output_path}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    output_dir = os.path.join(root_dir, "output")

    doi_output = os.path.join(output_dir, "doi_letter.docx")
    contents_output = os.path.join(output_dir, "contents_eng.docx")
    xml_output_name = os.path.join(output_dir, "crossref.xml")

    # Generate documents
    create_doi_letter_docx(xml_output_name, doi_output)
    create_contents_docx(xml_output_name, contents_output)
