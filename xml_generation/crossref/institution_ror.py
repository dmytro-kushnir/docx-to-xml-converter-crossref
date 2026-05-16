"""Map extracted affiliation lines to Crossref institution_name + ROR URL."""

import re
import unicodedata


def _normalize_key(text):
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = text.replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')
    return re.sub(r"\s+", " ", text)


def _matches_line(line_key, entry):
    name_key = _normalize_key(entry.get("name"))
    if line_key == name_key:
        return True
    for alias in entry.get("aliases") or []:
        if line_key == _normalize_key(alias):
            return True
        if _normalize_key(alias) in line_key or line_key in _normalize_key(alias):
            return True
    if name_key and (name_key in line_key or line_key in name_key):
        return True
    return False


def resolve_institution(affiliation_line, institutions_config, default_institution_id=None):
    """
    Return {"name": str, "ror": str} or None.
    institutions_config: dict id -> {name, ror, aliases?}
    """
    if not affiliation_line or not institutions_config:
        return None

    line_key = _normalize_key(affiliation_line)
    for entry in institutions_config.values():
        if _matches_line(line_key, entry):
            ror = (entry.get("ror") or "").strip()
            name = (entry.get("name") or "").strip()
            if name and ror:
                return {"name": name, "ror": ror}

    if default_institution_id:
        entry = institutions_config.get(default_institution_id)
        if entry:
            ror = (entry.get("ror") or "").strip()
            name = (entry.get("name") or "").strip()
            if name and ror:
                return {"name": name, "ror": ror}
    return None
