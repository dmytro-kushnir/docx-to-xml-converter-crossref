import re
from datetime import datetime
import xml.etree.ElementTree as ET
import lxml.etree as etree
import yaml
from docx_processing.extractors import sanitize_affiliation_lines_for_organization

# ---------- Load configuration (same style as your Crossref file) ----------
with open("config.yml", "r", encoding="utf-8") as config_file:
    config = yaml.safe_load(config_file)

PUBLICATION_YEAR = config["publication"]["year"]
PUBLICATION_MONTH = config["publication"]["month"]
JOURNAL_VOLUME = config["publication"]["volume"]
JOURNAL_ISSUE = config["publication"]["issue"]

JOURNAL_DOI = config["journal"]["doi"]
JOURNAL_URL = config["journal"]["base_url"].rstrip("/")
ISSN_PRINT = config["journal"]["issn"].get("print", "")
ISSN_ELECTRONIC = config["journal"]["issn"].get("electronic", "")


def month_to_issue_date(year: str, month: str) -> str:
    """Publication date YYYY-MM-DD for the issue (1st day of month by default)."""
    try:
        y = int(year); m = int(month)
        return f"{y:04d}-{m:02d}-01"
    except Exception:
        return datetime.utcnow().strftime("%Y-%m-%d")

def generate_doi(start_page: int) -> str:
    """Same DOI pattern you use for Crossref: <prefix><YYYY>.<II>.<SSS>."""
    return f"{JOURNAL_DOI}{int(PUBLICATION_YEAR)}.{int(JOURNAL_ISSUE):02d}.{int(start_page):03d}"

def extract_doi_from_string(s: str):
    """Pull DOI from a reference line if present."""
    if not s:
        return None
    m = re.search(r"\b10\.\d{4,9}/\S+\b", s)
    if m:
        return m.group(0).rstrip(".,;)")
    m = re.search(r"https?://doi\.org/(10\.\d{4,9}/\S+)", s, flags=re.IGNORECASE)
    if m:
        return m.group(1).rstrip(".,;)")
    return None

def parse_authors_simple(authors_text: str):
    """
    Very tolerant author parser for strings like:
      "Bybyk R.T., Nakonechnyi Y.M."
      "V.S. Ivkova, I.R. Opirskyi"
      "Kudriavtsev D.O., Mychuda L.Z."
    Returns a list of dicts with fields: name, surname, order, role, polishAffiliation
    """
    authors = []
    if not authors_text:
        return authors
    parts = [p.strip() for p in authors_text.split(",") if p.strip()]
    for idx, p in enumerate(parts, 1):
        # Pattern 1: "I.P. Surname"
        m = re.match(r"^(([A-Za-zА-Яа-яІіЇїЄєҐґ]\.){1,3})\s+([A-Za-zА-Яа-яІіЇїЄєҐґ'\-]+)$", p)
        if m:
            initials = re.findall(r"[A-Za-zА-Яа-яІіЇїЄєҐґ]", m.group(1))
            name = " ".join(initials)
            surname = m.group(3)
        else:
            # Pattern 2: "Surname I.P." or "Surname I.P" or "Surname I. P."
            tokens = p.replace(".", " ").split()
            if not tokens:
                continue
            surname = tokens[0]
            initials = [t[0] for t in tokens[1:] if t]
            name = " ".join(initials) if initials else ""
        authors.append({
            "name": name,
            "surname": surname,
            "order": str(idx),
            "role": "AUTHOR",
            "polishAffiliation": "false"
        })
    return authors

def _parse_keywords_line(text: str):
    if not text:
        return []
    items = [x.strip(" .;:,–—()[]") for x in re.split(r"[;,]", text) if x.strip()]
    return [x for x in items if 0 < len(x) <= 80][:20]


def split_multilingual_abstract_payload(abstract_text: str):
    """
    Parse EN/UK abstract and keyword sections from a single extracted abstract block.
    Uses labels when present and falls back to EN-only payload.
    """
    payload = {
        "en_abstract": "",
        "uk_abstract": "",
        "en_keywords": [],
        "uk_keywords": [],
    }
    if not abstract_text:
        return payload

    lines = [line.strip() for line in abstract_text.splitlines() if line.strip()]
    state = None

    for line in lines:
        en_abs_match = re.match(r"^abstract\s*[:.\-]?\s*(.*)$", line, flags=re.IGNORECASE)
        uk_abs_match = re.match(r"^анотац(?:ія|iя)\s*[:.\-]?\s*(.*)$", line, flags=re.IGNORECASE)
        en_kw_match = re.match(r"^keywords?\s*[:.\-]?\s*(.*)$", line, flags=re.IGNORECASE)
        uk_kw_match = re.match(r"^ключов[іi]\s+слова\s*[:.\-]?\s*(.*)$", line, flags=re.IGNORECASE)

        if en_abs_match:
            state = "en_abstract"
            rest = en_abs_match.group(1).strip()
            if rest:
                payload["en_abstract"] = f'{payload["en_abstract"]}\n{rest}'.strip()
            continue
        if uk_abs_match:
            state = "uk_abstract"
            rest = uk_abs_match.group(1).strip()
            if rest:
                payload["uk_abstract"] = f'{payload["uk_abstract"]}\n{rest}'.strip()
            continue
        if en_kw_match:
            state = None
            payload["en_keywords"].extend(_parse_keywords_line(en_kw_match.group(1)))
            continue
        if uk_kw_match:
            state = None
            payload["uk_keywords"].extend(_parse_keywords_line(uk_kw_match.group(1)))
            continue

        if state == "en_abstract":
            payload["en_abstract"] = f'{payload["en_abstract"]}\n{line}'.strip()
        elif state == "uk_abstract":
            payload["uk_abstract"] = f'{payload["uk_abstract"]}\n{line}'.strip()

    if not payload["en_abstract"]:
        cleaned_lines = [
            line for line in lines
            if not re.match(r"^(keywords?|ключов[іi]\s+слова)\s*[:.\-]?\s*", line, flags=re.IGNORECASE)
        ]
        payload["en_abstract"] = "\n".join(cleaned_lines).strip()

    return payload

# ---------- Builders (similar style/shape to your Crossref functions) ----------
def create_issue_element():
    """
    Creates the <issue> node with attributes (number, volume, year, publicationDate, numberOfArticles),
    and returns the Element so caller can append articles.
    """
    publication_date = month_to_issue_date(PUBLICATION_YEAR, PUBLICATION_MONTH)
    issue_attrs = {
        "number": str(JOURNAL_ISSUE),
        "volume": str(JOURNAL_VOLUME),
        "year": str(PUBLICATION_YEAR),
        "publicationDate": publication_date,
        "numberOfArticles": "0",  # we will overwrite after adding articles
    }
    return ET.Element("issue", issue_attrs)

def append_language_version(parent_el, language: str, title: str, abstract_text: str,
                            publication_date: str, page_from: int, page_to: int,
                            doi: str, pdf_url: str = None, keywords=None):
    lv = ET.SubElement(parent_el, "languageVersion", attrib={"language": language})
    if title:
        ET.SubElement(lv, "title").text = title
    if abstract_text:
        ET.SubElement(lv, "abstract").text = abstract_text
    if pdf_url:
        ET.SubElement(lv, "pdfFileUrl").text = pdf_url
    ET.SubElement(lv, "publicationDate").text = publication_date
    ET.SubElement(lv, "pageFrom").text = str(page_from)
    ET.SubElement(lv, "pageTo").text = str(page_to)
    if doi:
        ET.SubElement(lv, "doi").text = doi
    if keywords:
        ks = ET.SubElement(lv, "keywords")
        for k in keywords:
            ET.SubElement(ks, "keyword").text = k

def create_article_element(en_title, uk_title, authors_text, pages, refs, abstract_text, affiliation_lines):
    """
    Creates one <article> node (with EN languageVersion required, optional UK languageVersion,
    <authors>, <references>). Mirrors your Crossref article builder in spirit.
    """
    start_page, end_page = pages
    doi = generate_doi(start_page)
    publication_date = month_to_issue_date(PUBLICATION_YEAR, PUBLICATION_MONTH)

    article_el = ET.Element("article", attrib={"externalId": doi})
    ET.SubElement(article_el, "type").text = "ORIGINAL_ARTICLE"

    # EN/UK languageVersion payload extracted from the shared abstract block
    lang_payload = split_multilingual_abstract_payload(abstract_text)
    # If you want a predictable PDF URL, keep this; otherwise leave as None
    # pdf_url_en = f"{JOURNAL_URL}/all-volumes-and-issues/volume-{JOURNAL_VOLUME}-number-{JOURNAL_ISSUE}-{PUBLICATION_YEAR}/{slugify_title(en_title)}.pdf"
    pdf_url_en = None
    append_language_version(
        article_el, "en", en_title, lang_payload["en_abstract"], publication_date,
        start_page, end_page, doi, pdf_url=pdf_url_en, keywords=lang_payload["en_keywords"]
    )

    # UKR languageVersion with abstract/keywords when available
    if uk_title:
        append_language_version(
            article_el, "uk", uk_title, lang_payload["uk_abstract"], publication_date,
            start_page, end_page, doi, pdf_url=None, keywords=lang_payload["uk_keywords"]
        )

    # Authors
    parsed = parse_authors_simple(authors_text)
    org_lines = sanitize_affiliation_lines_for_organization(affiliation_lines or [])
    affiliation_text = "; ".join(org_lines) if org_lines else None
    if parsed:
        authors_el = ET.SubElement(article_el, "authors")
        for a in parsed:
            ae = ET.SubElement(authors_el, "author")
            if a.get("name"):    ET.SubElement(ae, "name").text = a["name"]
            if a.get("surname"): ET.SubElement(ae, "surname").text = a["surname"]
            if affiliation_text:
                ET.SubElement(ae, "instituteAffiliation").text = affiliation_text
            ET.SubElement(ae, "polishAffiliation").text = a.get("polishAffiliation", "false")
            ET.SubElement(ae, "order").text = a.get("order", "1")
            ET.SubElement(ae, "role").text = a.get("role", "AUTHOR")

    # References
    if refs:
        refs_el = ET.SubElement(article_el, "references")
        for i, r in enumerate(refs, 1):
            re_el = ET.SubElement(refs_el, "reference")
            ET.SubElement(re_el, "unparsedContent").text = r
            ET.SubElement(re_el, "order").text = str(i)
            r_doi = extract_doi_from_string(r)
            if r_doi:
                ET.SubElement(re_el, "doi").text = r_doi

    return article_el

# ---------- Main entrypoint (keeps your signature/name) ----------
def create_ici_copernicus_xml(articles_data):
    """
    Build the ICI Copernicus XML as a unicode string (same style as your Crossref create_full_xml).
    """
    # Root
    root = ET.Element("ici-import")

    # <journal issn="..."/>
    issn = ISSN_ELECTRONIC or ISSN_PRINT or ""
    ET.SubElement(root, "journal", attrib={"issn": issn})

    # <issue ...> + articles
    issue_el = create_issue_element()
    root.append(issue_el)

    for item in articles_data:
        en_title, uk_title, authors_text, pages, refs, abstract_text = item[:6]
        affiliation_lines = item[6] if len(item) > 6 else []
        article_el = create_article_element(
            en_title, uk_title, authors_text, pages, refs, abstract_text, affiliation_lines
        )
        issue_el.append(article_el)

    # Set numberOfArticles attribute at the end
    issue_el.set("numberOfArticles", str(len(articles_data)))

    # Pretty-print via lxml (same output pattern as in Crossref code)
    xml_str = etree.tostring(etree.fromstring(ET.tostring(root)), pretty_print=True, encoding="unicode")
    xml_with_decl = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'
    return xml_with_decl


# ---------- Optional: CLI demo ----------
if __name__ == "__main__":
    # Provide your real articles_data here (same shape you already have):
    demo_articles_data = []  # fill with your tuples
    print(create_ici_copernicus_xml(demo_articles_data))

