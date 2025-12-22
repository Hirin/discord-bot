"""
Document Utilities - PDF to images conversion
"""

import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Max file size: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf"}


def pdf_to_images(pdf_bytes: bytes, max_pages: int = 10, dpi: int = 150) -> list[str]:
    """
    Convert PDF pages to base64 encoded PNG images.
    
    Args:
        pdf_bytes: PDF file content
        max_pages: Maximum pages to convert
        dpi: Image resolution
        
    Returns:
        List of base64 encoded PNG images
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF not installed. Run: uv pip install pymupdf")
        return []
    
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []
        
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            
            # Render page to image
            pix = page.get_pixmap(dpi=dpi)
            img_bytes = pix.tobytes("png")
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")
            images.append(img_base64)
        
        doc.close()
        logger.info(f"Converted {len(images)} pages from PDF")
        return images
        
    except Exception as e:
        logger.error(f"Failed to convert PDF: {e}")
        return []


def validate_attachment(attachment) -> tuple[bool, Optional[str]]:
    """
    Validate Discord attachment for document upload.
    
    Returns:
        (is_valid, error_message)
    """
    filename = attachment.filename.lower()
    ext = "." + filename.split(".")[-1] if "." in filename else ""
    
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Chỉ hỗ trợ PDF (không phải {ext})"
    
    return True, None
