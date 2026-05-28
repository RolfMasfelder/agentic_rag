import logging

from .base import BaseParser, ParsedChunk, ParsedDocument

logger = logging.getLogger(__name__)

# Minimum number of text characters extracted by PyMuPDF per page before we
# consider the page to be image-only and fall back to OCR.
_OCR_TEXT_THRESHOLD = 20


def _ocr_page(page) -> str:  # type: ignore[no-untyped-def]
    """Run Tesseract OCR on a PyMuPDF page and return the extracted text.

    Requires ``pytesseract`` (in requirements.txt) and the ``tesseract-ocr``
    system package (installed via Dockerfile).  If unavailable at runtime,
    returns an empty string.
    """
    try:
        import pytesseract  # type: ignore[import-untyped]
        from PIL import Image  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("pytesseract not importable – OCR fallback unavailable.")
        return ""

    pix = page.get_pixmap(dpi=300)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return pytesseract.image_to_string(img)


class PDFParser(BaseParser):
    """Parse PDF files using PyMuPDF.

    Pages that contain very little selectable text are treated as scanned
    images and processed via Tesseract OCR (requires ``pytesseract`` and
    ``Pillow`` plus the ``tesseract`` system package).
    """

    def supports(self, mime_type: str) -> bool:
        return mime_type == "application/pdf"

    def parse(self, file_path: str) -> ParsedDocument:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        title = doc.metadata.get("title") or file_path.split("/")[-1]
        chunks: list[ParsedChunk] = []
        ocr_pages: list[int] = []

        for page_num, page in enumerate(doc, start=1):
            blocks = page.get_text("blocks")
            page_text = " ".join(b[4].strip() for b in blocks if b[4].strip())

            if len(page_text) < _OCR_TEXT_THRESHOLD:
                # Likely a scanned page – attempt OCR.
                ocr_text = _ocr_page(page)
                if ocr_text.strip():
                    ocr_pages.append(page_num)
                    chunks.append(
                        ParsedChunk(
                            content=ocr_text.strip(),
                            chunk_type="paragraph",
                            position=len(chunks),
                            page_number=page_num,
                            metadata={"ocr": True},
                        )
                    )
                continue

            for i, block in enumerate(blocks):
                text = block[4].strip()
                if not text:
                    continue
                chunks.append(
                    ParsedChunk(
                        content=text,
                        chunk_type="paragraph",
                        position=len(chunks),
                        page_number=page_num,
                        metadata={"block_index": i},
                    )
                )

        pdf_meta = dict(doc.metadata)
        if ocr_pages:
            pdf_meta["ocr_pages"] = ocr_pages
        return ParsedDocument(title=title, chunks=chunks, metadata=pdf_meta)
