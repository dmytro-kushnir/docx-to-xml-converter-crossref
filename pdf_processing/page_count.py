from PyPDF2 import PdfReader
import re
import json

def extract_pdf_articles_pages(pdf_path, marker="COMPUTER SYSTEMS AND NETWORKS"):
    reader = PdfReader(pdf_path)
    marker_pages = []

    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and marker in text:
            marker_pages.append(i + 1)  # 1-based PDF numbering

    if not marker_pages:
        raise ValueError("Маркер не знайдено у PDF.")

    offset = marker_pages[0] - 1  # фактична - друкована (яку приймаємо як 1)
    article_pages = []

    for i, real_page in enumerate(marker_pages):
        logical_start = real_page - offset
        logical_end = (
            marker_pages[i + 1] - 1 - offset
            if i + 1 < len(marker_pages)
            else len(reader.pages) - offset
        )
        article_pages.append({
            "start_page": logical_start,
            "end_page": logical_end
        })

    return article_pages


if __name__ == "__main__":
    pages = extract_pdf_articles_pages("")
    print(pages)

