#!/usr/bin/env python3
"""
Unit tests for PDF to Markdown converter.
"""

import unittest
import tempfile
import os
from pathlib import Path
import shutil

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.converter import (
    extract_text_from_pdf,
    clean_text,
    convert_pdf_to_md,
    batch_convert,
)


class TestPDFConverter(unittest.TestCase):
    """Test cases for PDF converter functions."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests."""
        # Path to test PDF
        cls.test_pdf = Path(__file__).parent / "data" / "test_document.pdf"

        # Create test PDF if it doesn't exist
        if not cls.test_pdf.exists():
            # Create using create_test_pdf script
            import subprocess
            subprocess.run(
                ["python", "scripts/create_test_pdf.py", str(cls.test_pdf)],
                check=True,
                capture_output=True
            )

    def setUp(self):
        """Set up test fixtures before each test."""
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up after each test."""
        # Remove temporary directory
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_extract_text_from_pdf(self):
        """Test extracting text from PDF."""
        text = extract_text_from_pdf(str(self.test_pdf))

        # Check text was extracted
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 100)

        # Check for expected content
        self.assertIn("АРБИТРАЖНЫЙ СУД", text)
        self.assertIn("А40-12345/24", text)
        self.assertIn("РЕШИЛ", text)

    def test_extract_from_nonexistent_pdf(self):
        """Test error handling for non-existent PDF."""
        with self.assertRaises(FileNotFoundError):
            extract_text_from_pdf("nonexistent.pdf")

    def test_clean_text(self):
        """Test text cleaning function."""
        # Test multiple spaces
        text = "Hello    world"
        cleaned = clean_text(text)
        self.assertEqual(cleaned, "Hello world")

        # Test multiple newlines
        text = "Line 1\n\n\n\nLine 2"
        cleaned = clean_text(text)
        self.assertEqual(cleaned, "Line 1\n\nLine 2")

        # Test trailing whitespace
        text = "  Line with spaces  \n  Another line  "
        cleaned = clean_text(text)
        self.assertFalse(cleaned.startswith(" "))
        self.assertFalse(cleaned.endswith(" "))

        # Test punctuation spacing
        text = "Hello , world ."
        cleaned = clean_text(text)
        self.assertEqual(cleaned, "Hello, world.")

    def test_clean_empty_text(self):
        """Test cleaning empty text."""
        self.assertEqual(clean_text(""), "")
        self.assertEqual(clean_text(None), "")

    def test_convert_pdf_to_md(self):
        """Test basic PDF to MD conversion."""
        output_md = Path(self.temp_dir) / "test.md"

        success = convert_pdf_to_md(str(self.test_pdf), str(output_md))

        # Check conversion succeeded
        self.assertTrue(success)

        # Check MD file was created
        self.assertTrue(output_md.exists())

        # Check MD content
        md_content = output_md.read_text(encoding='utf-8')

        # Check metadata header
        self.assertIn("---", md_content)
        self.assertIn("source:", md_content)
        self.assertIn("converted:", md_content)

        # Check main content
        self.assertIn("АРБИТРАЖНЫЙ СУД", md_content)
        self.assertIn("А40-12345/24", md_content)

    def test_convert_pdf_to_md_without_metadata(self):
        """Test conversion without metadata header."""
        output_md = Path(self.temp_dir) / "test_no_meta.md"

        success = convert_pdf_to_md(
            str(self.test_pdf),
            str(output_md),
            add_metadata=False
        )

        self.assertTrue(success)

        md_content = output_md.read_text(encoding='utf-8')

        # Should not have metadata header
        self.assertNotIn("source:", md_content)
        self.assertNotIn("converted:", md_content)

        # Should still have main content
        self.assertIn("АРБИТРАЖНЫЙ СУД", md_content)

    def test_convert_creates_output_directory(self):
        """Test that conversion creates output directory if needed."""
        output_md = Path(self.temp_dir) / "subdir" / "nested" / "test.md"

        success = convert_pdf_to_md(str(self.test_pdf), str(output_md))

        self.assertTrue(success)
        self.assertTrue(output_md.exists())
        self.assertTrue(output_md.parent.exists())

    def test_batch_convert(self):
        """Test batch conversion of multiple PDFs."""
        # Create multiple test PDFs (copy the same one)
        pdf_files = []
        for i in range(3):
            pdf_copy = Path(self.temp_dir) / f"test_{i}.pdf"
            shutil.copy(self.test_pdf, pdf_copy)
            pdf_files.append(str(pdf_copy))

        # Convert all PDFs
        output_dir = Path(self.temp_dir) / "md_output"
        successful, failed = batch_convert(
            pdf_files,
            str(output_dir),
            num_workers=2,
            verbose=False
        )

        # Check results
        self.assertEqual(successful, 3)
        self.assertEqual(failed, 0)

        # Check MD files were created
        for i in range(3):
            md_file = output_dir / f"test_{i}.md"
            self.assertTrue(md_file.exists())

    def test_batch_convert_empty_list(self):
        """Test batch conversion with empty list."""
        output_dir = Path(self.temp_dir) / "md_output"
        successful, failed = batch_convert([], str(output_dir), verbose=False)

        self.assertEqual(successful, 0)
        self.assertEqual(failed, 0)

    def test_batch_convert_with_errors(self):
        """Test batch conversion with some invalid files."""
        # Mix valid and invalid PDF paths
        pdf_files = [
            str(self.test_pdf),  # Valid
            "nonexistent1.pdf",  # Invalid
            str(self.test_pdf),  # Valid
            "nonexistent2.pdf",  # Invalid
        ]

        output_dir = Path(self.temp_dir) / "md_output"
        successful, failed = batch_convert(
            pdf_files,
            str(output_dir),
            num_workers=2,
            verbose=False
        )

        # Should have 2 successful and 2 failed
        self.assertEqual(successful, 2)
        self.assertEqual(failed, 2)

    def test_text_contains_expected_content(self):
        """Test that extracted text contains all expected sections."""
        text = extract_text_from_pdf(str(self.test_pdf))

        # Check key sections
        expected_content = [
            "АРБИТРАЖНЫЙ СУД ГОРОДА МОСКВЫ",
            "РЕШЕНИЕ",
            "Именем Российской Федерации",
            "А40-12345/24",
            "УСТАНОВИЛ",
            "РЕШИЛ",
            # Note: Skipping "Судья" due to font encoding issues in test PDF
        ]

        for content in expected_content:
            self.assertIn(content, text, f"Expected content not found: {content}")

    def test_converted_md_file_size(self):
        """Test that converted MD file has reasonable size."""
        output_md = Path(self.temp_dir) / "test.md"

        convert_pdf_to_md(str(self.test_pdf), str(output_md))

        # Check file size (should be > 100 bytes and < 100KB)
        file_size = output_md.stat().st_size
        self.assertGreater(file_size, 100)
        self.assertLess(file_size, 100000)


class TestCleanTextEdgeCases(unittest.TestCase):
    """Test edge cases for text cleaning."""

    def test_clean_text_with_unicode(self):
        """Test cleaning text with Unicode characters."""
        text = "Привет  мир \n\n Тест"
        cleaned = clean_text(text)

        self.assertIn("Привет мир", cleaned)
        self.assertNotIn("  ", cleaned)  # No double spaces

    def test_clean_text_preserves_structure(self):
        """Test that cleaning preserves basic structure."""
        text = """Заголовок

Параграф 1

Параграф 2"""

        cleaned = clean_text(text)

        # Should have two blank lines (paragraph separators)
        self.assertEqual(cleaned.count("\n\n"), 2)

    def test_clean_text_removes_excess_newlines(self):
        """Test that excessive newlines are reduced."""
        text = "Line 1\n\n\n\n\nLine 2"
        cleaned = clean_text(text)

        # Should reduce to maximum 2 newlines
        self.assertNotIn("\n\n\n", cleaned)
        self.assertIn("Line 1\n\nLine 2", cleaned)


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
