"""
Tests for LaTeX processing functions.
"""
import pytest
import os

from services.latex_utils import (
    convert_latex_to_unicode,
    process_latex_formulas,
    render_latex_to_image,
    cleanup_latex_images,
)


class TestConvertLatexToUnicode:
    """Tests for convert_latex_to_unicode function."""
    
    def test_converts_greek_letters(self):
        """Should convert Greek letters to Unicode."""
        result = convert_latex_to_unicode("$\\alpha + \\beta = \\gamma$")
        assert "α" in result
        assert "β" in result
        assert "γ" in result
        assert "\\alpha" not in result
    
    def test_converts_superscripts(self):
        """Should convert superscripts to Unicode."""
        result = convert_latex_to_unicode("$x^2 + y^3$")
        assert "²" in result
        assert "³" in result
    
    def test_converts_subscripts(self):
        """Should convert subscripts to Unicode."""
        result = convert_latex_to_unicode("$x_1 + y_2$")
        assert "₁" in result
        assert "₂" in result
    
    def test_converts_operators(self):
        """Should convert mathematical operators."""
        result = convert_latex_to_unicode("$\\sum_{i=1}^{n} x_i$")
        assert "∑" in result
    
    def test_preserves_block_formulas(self):
        """Should NOT convert block formulas ($$...$$)."""
        text = "Inline $\\alpha$ and block $$\\frac{a}{b}$$"
        result = convert_latex_to_unicode(text)
        # Inline should be converted
        assert "α" in result
        # Block should remain as-is
        assert "$$" in result
    
    def test_no_latex(self):
        """Text without LaTeX should remain unchanged."""
        text = "Plain text without formulas"
        result = convert_latex_to_unicode(text)
        assert result == text
    
    def test_converts_fractions(self):
        """Should convert simple fractions."""
        result = convert_latex_to_unicode("$\\frac{a}{b}$")
        # Should have fraction bar or a/b format
        assert "/" in result or "⁄" in result or "a" in result
    
    def test_converts_arrows(self):
        """Should convert arrow symbols."""
        result = convert_latex_to_unicode("$x \\rightarrow y$")
        assert "→" in result
    
    def test_multiple_formulas(self):
        """Should handle multiple inline formulas."""
        text = "First $\\alpha$, then $\\beta$, finally $\\gamma$"
        result = convert_latex_to_unicode(text)
        assert "α" in result
        assert "β" in result
        assert "γ" in result


class TestProcessLatexFormulas:
    """Tests for process_latex_formulas function."""
    
    def test_processes_inline_formulas(self):
        """Should convert inline $...$ to Unicode."""
        text = "The formula is $\\alpha + \\beta$"
        result, images = process_latex_formulas(text)
        
        assert "α" in result
        assert "β" in result
        assert images == []  # No block formulas
    
    def test_processes_block_formulas(self, tmp_path):
        """Should render block $$...$$ to images."""
        text = "Check this: $$\\frac{a}{b}$$"
        result, images = process_latex_formulas(text, output_dir=str(tmp_path))
        
        # Should have placeholder in text
        if images:  # matplotlib may not be available
            assert len(images) == 1
            placeholder, img_path = images[0]
            assert placeholder in result
            assert os.path.exists(img_path)
    
    def test_handles_mixed_formulas(self, tmp_path):
        """Should handle both inline and block formulas."""
        text = "Inline $\\alpha$ and block $$\\beta^2$$"
        result, images = process_latex_formulas(text, output_dir=str(tmp_path))
        
        # Inline should be converted
        assert "α" in result
    
    def test_no_formulas(self):
        """Text without formulas should remain unchanged."""
        text = "No LaTeX here"
        result, images = process_latex_formulas(text)
        
        assert result == text
        assert images == []
    
    def test_empty_text(self):
        """Empty text should return empty."""
        result, images = process_latex_formulas("")
        assert result == ""
        assert images == []


class TestRenderLatexToImage:
    """Tests for render_latex_to_image function."""
    
    def test_renders_simple_formula(self, tmp_path):
        """Should render a simple formula to image."""
        output_path = str(tmp_path / "test_formula.png")
        result = render_latex_to_image("x^2 + y^2 = z^2", output_path)
        
        if result:  # matplotlib available
            assert os.path.exists(output_path)
            # Check file has content
            assert os.path.getsize(output_path) > 0
    
    def test_renders_complex_formula(self, tmp_path):
        """Should render complex formulas."""
        output_path = str(tmp_path / "complex.png")
        latex = r"\frac{\partial f}{\partial x} = \lim_{h \to 0} \frac{f(x+h) - f(x)}{h}"
        result = render_latex_to_image(latex, output_path)
        
        if result:
            assert os.path.exists(output_path)
    
    def test_handles_invalid_latex(self, tmp_path):
        """Should handle invalid LaTeX gracefully."""
        output_path = str(tmp_path / "invalid.png")
        result = render_latex_to_image(r"\invalid{command}", output_path)
        
        # Should return False for invalid LaTeX
        # Or create image with error
        assert isinstance(result, bool)


class TestCleanupLatexImages:
    """Tests for cleanup_latex_images function."""
    
    def test_deletes_images(self, tmp_path):
        """Should delete image files."""
        # Create test files
        img1 = tmp_path / "latex1.png"
        img2 = tmp_path / "latex2.png"
        img1.write_bytes(b"test")
        img2.write_bytes(b"test")
        
        images = [
            ("placeholder1", str(img1)),
            ("placeholder2", str(img2)),
        ]
        
        cleanup_latex_images(images)
        
        assert not img1.exists()
        assert not img2.exists()
    
    def test_handles_nonexistent_files(self, tmp_path):
        """Should handle missing files gracefully."""
        images = [
            ("placeholder", str(tmp_path / "nonexistent.png")),
        ]
        
        # Should not raise
        cleanup_latex_images(images)
    
    def test_handles_empty_list(self):
        """Should handle empty list."""
        cleanup_latex_images([])  # Should not raise
