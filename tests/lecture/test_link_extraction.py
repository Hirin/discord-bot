"""
Tests for link extraction functions.
"""
import pytest

from services.slides import (
    extract_links_from_pdf,
    format_pdf_links_for_prompt,
    get_page_image,
)


class TestExtractLinksFromPdf:
    """Tests for extract_links_from_pdf function."""
    
    def test_extracts_links_from_pdf(self, sample_pdf_with_links):
        """Should extract hyperlinks from PDF."""
        links = extract_links_from_pdf(sample_pdf_with_links)
        
        assert len(links) == 2
        # Links are tuples of (page_num, url)
        assert links[0][0] == 1  # Page 1
        assert "example.com" in links[0][1]
        assert links[1][0] == 2  # Page 2
        assert "docs.google.com" in links[1][1]
    
    def test_nonexistent_file(self):
        """Should return empty list for nonexistent file."""
        links = extract_links_from_pdf("/nonexistent/path.pdf")
        assert links == []
    
    def test_pdf_without_links(self, tmp_path):
        """Should return empty list for PDF without links."""
        try:
            import fitz
        except ImportError:
            pytest.skip("PyMuPDF not installed")
        
        pdf_path = tmp_path / "no_links.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "No links here")
        doc.save(str(pdf_path))
        doc.close()
        
        links = extract_links_from_pdf(str(pdf_path))
        assert links == []


class TestFormatPdfLinksForPrompt:
    """Tests for format_pdf_links_for_prompt function."""
    
    def test_formats_links(self):
        """Should format links with page numbers."""
        links = [(1, "https://example.com"), (3, "https://docs.google.com")]
        result = format_pdf_links_for_prompt(links)
        
        assert "Page 1" in result
        assert "Page 3" in result
        assert "<https://example.com>" in result
    
    def test_empty_links(self):
        """Empty list should return empty string."""
        result = format_pdf_links_for_prompt([])
        assert result == ""
    
    def test_single_link(self):
        """Single link should format correctly."""
        links = [(5, "https://example.com")]
        result = format_pdf_links_for_prompt(links)
        
        assert "Page 5" in result
        assert "<https://example.com>" in result


class TestGetPageImage:
    """Tests for get_page_image function."""
    
    def test_valid_page_number(self):
        """Should return image path for valid page number."""
        image_paths = ["/tmp/page_001.jpg", "/tmp/page_002.jpg", "/tmp/page_003.jpg"]
        
        assert get_page_image(image_paths, 1) == "/tmp/page_001.jpg"
        assert get_page_image(image_paths, 2) == "/tmp/page_002.jpg"
        assert get_page_image(image_paths, 3) == "/tmp/page_003.jpg"
    
    def test_invalid_page_number(self):
        """Should return None for invalid page number."""
        image_paths = ["/tmp/page_001.jpg", "/tmp/page_002.jpg"]
        
        assert get_page_image(image_paths, 0) is None
        assert get_page_image(image_paths, 3) is None
        assert get_page_image(image_paths, -1) is None
    
    def test_empty_list(self):
        """Should return None for empty list."""
        assert get_page_image([], 1) is None
    
    def test_none_list(self):
        """Should handle None input gracefully."""
        assert get_page_image(None, 1) is None
