import re

def extract_ukrainian_title(paragraphs):
    """Extracts the Ukrainian title, which is the paragraph after the one containing 'УДК'."""
    ukrainian_title = "Ukrainian title not found."
    for i, paragraph in enumerate(paragraphs):
        if "УДК" in paragraph:
            if i + 1 < len(paragraphs):
                ukrainian_title = paragraphs[i + 1]
            break
    return ukrainian_title

def extract_literature(paragraphs):
    """Extracts all literature references from the paragraphs."""
    literature_references = []
    found_literature = False
    for paragraph in paragraphs:
        if "Список літератури" in paragraph or re.search(r"\b(literature|references)\b", paragraph, re.IGNORECASE):
            found_literature = True
            continue
        if found_literature:
            # Check for a more flexible reference pattern
            if re.search(r"(doi:|vol\.|pp\.|\(\d{4}\)|\d{4}|Retrieved|http|https|Available:)", paragraph, re.IGNORECASE):
                literature_references.append(paragraph)
            else:
                # Stop if no longer in the literature section
                break
    return literature_references

def extract_english_title(paragraphs, literature_references):
    """Extracts the English title, which is the paragraph after the last literature reference."""
    english_title = "English title not found."
    if literature_references:
        last_reference = literature_references[-1]
        last_index = paragraphs.index(last_reference)
        if last_index + 1 < len(paragraphs):
            english_title = paragraphs[last_index + 1]
    return english_title

def extract_authors(paragraphs, is_ukrainian=False):
    """Extracts authors' names from the paragraphs.

    :param paragraphs: List of paragraphs from the DOCX file.
    :param is_ukrainian: Boolean flag indicating whether the text is in Ukrainian.
    :return: Extracted authors' names.
    """
    authors_text = "Authors not found."

    for paragraph in paragraphs:
        if paragraph.startswith("©"):
            # If extracting English authors, ensure no Cyrillic characters
            if not is_ukrainian and re.search(r"[А-Яа-яІЇЄҐіїєґ]", paragraph):
                continue  # Skip this paragraph as it contains Cyrillic

            # Extract authors after '©' and clean year if present
            authors_text = paragraph[1:].strip()
            authors_text = re.sub(r"\s\d{4}$", "", authors_text).strip()
            break

    return authors_text

def extract_abstract(paragraphs):
    """Extracts the abstract from the paragraphs."""
    abstract_text = "Abstract not found."
    abstract_start = None
    abstract_end = None
    for i, paragraph in enumerate(paragraphs):
        # Check if the paragraph starts with "©" and contains only Latin characters
        if re.match(r"^©", paragraph, re.IGNORECASE) and not re.search(r"[А-Яа-яІЇЄҐіїєґ]", paragraph):
            abstract_start = i
            break
    if abstract_start is not None:
        abstract_text = "\n".join(paragraphs[abstract_start + 1:abstract_end]).strip() if abstract_end else "\n".join(paragraphs[abstract_start + 1:]).strip()
    return abstract_text
