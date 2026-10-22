"""Map extracted affiliation lines to Crossref institution_name + ROR URL."""

import os
import re
import unicodedata

import yaml

# The registry is an append-only reference table that grows every issue, so it
# lives in its own file rather than in config.yml.
INSTITUTIONS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "institutions.yml",
)


def load_institutions(path=INSTITUTIONS_FILE):
    """The id -> {name, ror, aliases?} registry, or {} when there is none.

    Accepts the file either wrapped in a top-level ``institutions:`` key or as
    the bare mapping, so moving the block out of config.yml needed no reindent.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        return {}
    if isinstance(data, dict) and "institutions" in data:
        data = data["institutions"] or {}
    return data if isinstance(data, dict) else {}


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
