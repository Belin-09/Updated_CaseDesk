from docx import Document
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

def iter_block_items(parent):
    """Iterate through all paragraphs and tables sequentially."""
    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("Unsupported parent element")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

def extract_from_docx(file_path: str) -> tuple[str, None]:
    """Extract text from a .docx file sequentially to preserve reading order."""
    text = ""
    try:
        doc = Document(file_path)
        for block in iter_block_items(doc):
            if isinstance(block, Paragraph):
                if block.text.strip():
                    text += block.text + "\n"
            elif isinstance(block, Table):
                for row in block.rows:
                    for cell in row.cells:
                        # Extract paragraphs inside the cell sequentially
                        for nested_block in iter_block_items(cell):
                            if isinstance(nested_block, Paragraph) and nested_block.text.strip():
                                text += nested_block.text + "\n"
    except Exception as e:
        raise RuntimeError(f"python-docx failed: {str(e)}")

    return text.strip(), None