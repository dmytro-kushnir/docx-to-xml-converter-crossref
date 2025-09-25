from docx import Document
import os
import re
from typing import List, Tuple

# Canonical titles from template
REQUIRED_SECTIONS = [
    "Вступ",
    "Огляд літературних джерел",
    "Постановка задачі",
    "Результати дослідження",
    "Висновки",
    "Список літератури",
]

def _normalize(s: str) -> str:
    """Normalize text: trim, collapse spaces, drop leading numbering like '3. ' or '2.1 '."""
    s = s.replace("\u00A0", " ")  # NBSP → space
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    # Remove leading numbering patterns: 1. , 2.1 , 3) etc.
    s = re.sub(r"^\d+(\.\d+)*[.)]?\s*", "", s)
    return s

def extract_paragraph_texts(docx_path: str) -> List[str]:
    doc = Document(docx_path)
    return [_normalize(p.text) for p in doc.paragraphs if _normalize(p.text)]

def check_main_sections_present(docx_path: str) -> Tuple[List[str], List[str]]:
    paras = extract_paragraph_texts(docx_path)
    present, missing = [], []
    for title in REQUIRED_SECTIONS:
        if title in paras:
            present.append(title)
        else:
            missing.append(title)
    return present, missing

def report_for_file(docx_path: str) -> str:
    present, missing = check_main_sections_present(docx_path)
    if missing:
        return (
            f"Документ: {os.path.basename(docx_path)}\n"
            f"❌ Відсутні розділи: {', '.join(missing)}\n"
        )
    else:
        return (
            f"Документ: {os.path.basename(docx_path)}\n"
            f"✅ Усі розділи присутні\n"
        )

def validate_folder(folder_path: str) -> List[str]:
    reports = []
    for name in sorted(os.listdir(folder_path)):
        if name.lower().endswith(".docx"):
            reports.append(report_for_file(os.path.join(folder_path, name)))
    return reports

if __name__ == "__main__":
    FOLDER_PATH = ""
    for rep in validate_folder(FOLDER_PATH):
        print(rep)
