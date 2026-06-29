from docx import Document


def extract_from_docx(file_path: str) -> tuple[str, None]:
    """Extract text from a .docx file using python-docx."""
    text = ""
    try:
        doc = Document(file_path)
        for para in doc.paragraphs:
            if para.text.strip():
                text += para.text + "\n"

        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text += cell.text + "\n"

    except Exception as e:
        raise RuntimeError(f"python-docx failed: {str(e)}")

    return text.strip(), None