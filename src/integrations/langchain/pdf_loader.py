"""Extração do texto do PDF com PyPDFLoader (LangChain), devolvendo tipos do projeto."""

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader

from src.rag.document_loader import DEFAULT_PDF, DocumentError, check_lines_are_readable, check_pages_have_text
from src.rag.models import Page


def load_pdf_pages(pdf_path: Path | str = DEFAULT_PDF) -> list[Page]:
    """Lê o PDF página a página e confere que todas têm texto legível.

    `extraction_mode="layout"` é necessário: neste PDF cada palavra é um objeto de texto
    separado, e o modo padrão devolve uma palavra por linha ("Empório\\n \\nda\\n \\nMúsica"),
    o que destrói os títulos de seção. O modo layout reconstrói as linhas pela posição.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise DocumentError(f"PDF não encontrado: {path}")
    documents = PyPDFLoader(str(path), extraction_mode="layout").load()
    pages = [Page(number=doc.metadata["page"] + 1, text=doc.page_content) for doc in documents]  # metadata['page'] começa em 0
    check_pages_have_text(pages)
    check_lines_are_readable(pages)
    return pages