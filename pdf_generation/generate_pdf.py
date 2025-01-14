import os
import subprocess
import shutil
import sys
from docx_processing.parse import process_multiple_docs

def _get_soffice_path():
    """
    Locate the LibreOffice 'soffice' executable.
    Returns the full path to 'soffice' if found, or None if not found.
    """
    soffice_path = shutil.which("soffice")
    if soffice_path:
        return soffice_path

    # Handle common installation paths for Windows
    if os.name == "nt":  # Windows
        possible_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path

    return None

def _check_libreoffice_installed():
    """
    Check if LibreOffice is installed by verifying the presence of 'soffice'.
    """
    soffice_path = _get_soffice_path()
    if soffice_path is None:
        print("Error: LibreOffice is not installed or 'soffice' is not in your PATH.")
        print("Please install LibreOffice and ensure 'soffice' is accessible.")
        sys.exit(1)
    return soffice_path

def _convert_docx_to_pdf(docx_path, output_path):
    """
    Converts a single DOCX file to PDF using LibreOffice.
    """
    try:
        subprocess.run([
            "soffice", "--headless", "--convert-to", "pdf", "--outdir",
            os.path.dirname(output_path), docx_path
        ], check=True)
        print(f"Converted: {docx_path} -> {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to convert {docx_path}: {e}")

def process_and_convert_docs(input_folder, output_folder):
    """
    Processes multiple DOCX files and converts them to PDFs.
    """
    # Ensure LibreOffice is installed
    _check_libreoffice_installed()
    # Process DOCX files
    all_docs = process_multiple_docs(input_folder)

    # Ensure output folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Convert each DOCX to PDF
    for doc in process_multiple_docs(input_folder):
        input_path = os.path.join(input_folder, doc[0])  # filename
        output_path = os.path.join(output_folder, doc[0].replace(".docx", ".pdf"))
        _convert_docx_to_pdf(input_path, output_path)

if __name__ == "__main__":
    input_folder = ""
    output_folder = "output/pdfs"
    process_and_convert_docs(input_folder, output_folder)