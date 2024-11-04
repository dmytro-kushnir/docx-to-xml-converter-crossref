import zipfile
import xml.dom.minidom

def get_page_count_from_metadata(docx_path):
    """Gets the page count from the document metadata."""
    try:
        with zipfile.ZipFile(docx_path) as document:
            dxml = document.read('docProps/app.xml')
            uglyXml = xml.dom.minidom.parseString(dxml)
            page_count = int(uglyXml.getElementsByTagName('Pages')[0].childNodes[0].nodeValue)
            return page_count
    except Exception as e:
        print(f"Error reading page count from metadata: {e}")
        return 1  # Default to 1 page if metadata is not available or an error occurs
