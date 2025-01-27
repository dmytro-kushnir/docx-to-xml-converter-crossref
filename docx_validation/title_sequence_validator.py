from docx import Document
import re
import os

# Define expected title patterns with human-readable labels
EXPECTED_SEQUENCE = [
    (r"^DOI: https?://.+", "DOI"),
    (r"^УДК [\d.,\s]+", "УДК"),
    (r"^[А-ЯІЇЄҐа-яіїєґ\s\-,]+", "Назва статті (українською)"),  # Ukrainian title can be text with specific characters
    (r"^(?:[А-ЯІЇЄҐа-яіїєґ]{1,2}\.[А-ЯІЇЄҐа-яіїєґ]{1,2}\.\s*[А-ЯІЇЄҐа-яіїєґ]+)(?:,\s*[А-ЯІЇЄҐа-яіїєґ]{1,2}\.[А-ЯІЇЄҐа-яіїєґ]{1,2}\.\s*[А-ЯІЇЄҐа-яіїєґ]+)*$",
    "Автори (перший раз, формат І.П. Прізвище, І.П. Прізвище)"),
    (r"^\d?[А-ЯІЇЄҐа-яіїєґ\s\-,]+", "Назва університету та кафедра (може бути декілька рядків)"),
    (r"^Е-mail: (\S+@\S+\.[a-z]{2,})(,\s*\S+@\S+\.[a-z]{2,})*$", "E-mail (може бути декілька)"),
    (
    r"^©\s*[А-ЯІЇЄҐа-яіїєґ]{1,2}\.[А-ЯІЇЄҐа-яіїєґ]{1,2}\.,\s*[А-ЯІЇЄҐа-яіїєґ]{1,2}\.[А-ЯІЇЄҐа-яіїєґ]{1,2}\.[А-ЯІЇЄҐа-яіїєґ\s]+\s*\d{4}$",
    "Автори (з рік та ©, формат Прізвище І.П.)"),
    (r"^Анотація$", "Анотація"),
    (r"^Вступ$", "Вступ"),
    (r"^Огляд літературних джерел$", "Огляд літературних джерел"),
    (r"^Постановка задачі$", "Постановка задачі"),
    (r"^Результати дослідження$", "Результати дослідження"),
    (r"^Висновки$", "Висновки"),
    (r"^Список літератури$", "Список літератури"),
    (r"^[A-Za-z\s\-,]+", "Назва статті (англійською)"),  # English title with specific characters
    (r"^©\s*[A-Z]{1}\.[A-Za-z]+,\s*[A-Z]{1}\.[A-Za-z]+\s*\d{4}$", "Автори (англійською, з рік та ©)"),
    (r"^<Name of the university>$", "Назва університету (англійською)"),
    (r"^Department .+$", "Кафедра (англійською)"),
    (r"^E-mail: .+$", "E-mail (англійською)"),
]


def validate_docx_structure(filepath):
    """Validate the structure of a DOCX document."""
    doc = Document(filepath)
    titles = [para.text.strip() for para in doc.paragraphs if para.text.strip()]

    errors = []
    index = 0

    for entry in EXPECTED_SEQUENCE:
        pattern, label = entry[:2]

        while index < len(titles) and not re.match(pattern, titles[index]):
            index += 1

        if index >= len(titles):
            errors.append(f"Відсутній або неправильно розташований розділ: {label}")
        else:
            index += 1  # Move to the next section

    return errors


def format_validation_report(errors, filename):
    """Generate a validation report summarizing detected errors."""
    if errors:
        report = f"Документ: {filename}\n\nВиявлені помилки:\n" + "\n".join(f"- {error}" for error in errors)
    else:
        report = f"Документ: {filename} пройшов перевірку."
    return report


def validate_folder(folder_path):
    """Validate all DOCX files in a folder."""
    reports = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".docx"):
            filepath = os.path.join(folder_path, filename)
            errors = validate_docx_structure(filepath)
            report = format_validation_report(errors, filename)
            reports.append(report)
    return reports


def main(folder_path):
    reports = validate_folder(folder_path)
    for report in reports:
        print(report)


if __name__ == "__main__":
    FOLDER_PATH = ""
    main(FOLDER_PATH)