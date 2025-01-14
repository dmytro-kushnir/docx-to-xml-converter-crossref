import os
from PyPDF2 import PdfMerger

def merge_pdfs_alphabetically(input_folder, output_file):
    """
    Merges all PDF files from the input folder into a single PDF, sorted alphabetically by filename.

    Args:
        input_folder (str): Path to the folder containing PDF files.
        output_file (str): Path for the merged output PDF.
    """
    merger = PdfMerger()

    # Get a sorted list of PDF files (alphabetical, supports Cyrillic)
    pdf_files = sorted(
        [f for f in os.listdir(input_folder) if f.lower().endswith(".pdf")],
        key=lambda x: x.lower()
    )

    if not pdf_files:
        print("No PDF files found in the input folder.")
        return

    # Merge PDFs
    for pdf in pdf_files:
        pdf_path = os.path.join(input_folder, pdf)
        print(f"Adding {pdf_path} to the merger...")
        merger.append(pdf_path)

    # Write the merged PDF to the output file
    with open(output_file, "wb") as output:
        merger.write(output)
    print(f"Merged PDF saved as: {output_file}")

    # Close the merger
    merger.close()

if __name__ == "__main__":
    input_folder = "output/pdfs"
    output_file = "output/merged.pdf"
    merge_pdfs_alphabetically(input_folder, output_file)
