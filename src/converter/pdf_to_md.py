#!/usr/bin/env python3
"""
PDF to Markdown converter for court documents.

Features:
- Extract text from PDF files using pdfplumber
- Clean and format text for Markdown
- Batch processing with multiprocessing
- Performance optimization for large-scale conversion
"""

import re
from pathlib import Path
from typing import List, Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
import time

try:
    import pdfplumber
except ImportError:
    raise ImportError(
        "pdfplumber is required. Install it with: pip install pdfplumber"
    )


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text content from PDF file.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Extracted text as string

    Raises:
        FileNotFoundError: If PDF file doesn't exist
        Exception: If PDF cannot be opened or text cannot be extracted
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    text_parts = []

    try:
        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Extract text from page
                page_text = page.extract_text()

                if page_text:
                    text_parts.append(page_text)

        # Combine all pages
        full_text = "\n\n".join(text_parts)
        return full_text

    except Exception as e:
        raise Exception(f"Error extracting text from {pdf_path}: {e}")


def clean_text(text: str) -> str:
    """
    Clean extracted text for better Markdown formatting.

    Cleaning operations:
    - Remove excessive whitespace
    - Normalize line breaks
    - Remove page numbers at bottom
    - Fix common OCR artifacts (though PDFs have text, not OCR)
    - Normalize punctuation spacing

    Args:
        text: Raw extracted text

    Returns:
        Cleaned text
    """
    if not text:
        return ""

    # Replace multiple spaces with single space
    text = re.sub(r' {2,}', ' ', text)

    # Normalize line breaks - max 2 consecutive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove trailing/leading whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    # Remove common page number patterns at line ends
    # Patterns like "Страница 1 из 10" or just "1"
    text = re.sub(r'\n\s*Страница\s+\d+\s+из\s+\d+\s*\n', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'\n\s*\d+\s*\n$', '\n', text)

    # Fix spacing around punctuation
    text = re.sub(r'\s+([,.;:!?])', r'\1', text)  # Remove space before punctuation
    text = re.sub(r'([,.;:!?])(?=[А-ЯA-Z])', r'\1 ', text)  # Add space after punctuation before capital

    # Remove multiple consecutive blank lines
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)

    # Final trim
    text = text.strip()

    return text


def convert_pdf_to_md(pdf_path: str, md_path: str, add_metadata: bool = True) -> bool:
    """
    Convert PDF file to Markdown format.

    Args:
        pdf_path: Path to source PDF file
        md_path: Path to output Markdown file
        add_metadata: Whether to add document metadata header (default: True)

    Returns:
        True if successful, False otherwise
    """
    try:
        # Extract text
        raw_text = extract_text_from_pdf(pdf_path)

        # Clean text
        cleaned_text = clean_text(raw_text)

        # Create output directory if needed
        md_file = Path(md_path)
        md_file.parent.mkdir(parents=True, exist_ok=True)

        # Prepare Markdown content
        md_content = []

        if add_metadata:
            # Add metadata header
            pdf_name = Path(pdf_path).name
            md_content.append("---")
            md_content.append(f"source: {pdf_name}")
            md_content.append(f"converted: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            md_content.append("---")
            md_content.append("")

        # Add main content
        md_content.append(cleaned_text)

        # Write to file
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_content))

        return True

    except Exception as e:
        print(f"Error converting {pdf_path} to Markdown: {e}")
        return False


def _convert_single_pdf(args: Tuple[str, str, bool]) -> Tuple[str, bool, Optional[str]]:
    """
    Helper function for parallel processing.

    Args:
        args: Tuple of (pdf_path, md_path, add_metadata)

    Returns:
        Tuple of (pdf_path, success, error_message)
    """
    pdf_path, md_path, add_metadata = args

    try:
        success = convert_pdf_to_md(pdf_path, md_path, add_metadata)
        return (pdf_path, success, None)
    except Exception as e:
        return (pdf_path, False, str(e))


def batch_convert(
    pdf_files: List[str],
    output_dir: str,
    num_workers: int = 4,
    add_metadata: bool = True,
    verbose: bool = True
) -> Tuple[int, int]:
    """
    Convert multiple PDF files to Markdown in parallel.

    Args:
        pdf_files: List of PDF file paths
        output_dir: Directory for output Markdown files
        num_workers: Number of parallel workers (default: 4)
        add_metadata: Whether to add metadata headers (default: True)
        verbose: Print progress messages (default: True)

    Returns:
        Tuple of (successful_count, failed_count)
    """
    if not pdf_files:
        return (0, 0)

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Prepare conversion tasks
    tasks = []
    for pdf_file in pdf_files:
        pdf_path = Path(pdf_file)
        # Generate MD filename
        md_filename = pdf_path.stem + ".md"
        md_path = output_path / md_filename
        tasks.append((str(pdf_path), str(md_path), add_metadata))

    # Track progress
    successful = 0
    failed = 0
    start_time = time.time()

    if verbose:
        print(f"Converting {len(tasks)} PDF files using {num_workers} workers...")
        print()

    # Process in parallel
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        # Submit all tasks
        futures = {executor.submit(_convert_single_pdf, task): task for task in tasks}

        # Process results as they complete
        for i, future in enumerate(as_completed(futures), 1):
            pdf_path, success, error = future.result()

            if success:
                successful += 1
                if verbose:
                    print(f"✓ [{i}/{len(tasks)}] {Path(pdf_path).name}")
            else:
                failed += 1
                if verbose:
                    error_msg = f" ({error})" if error else ""
                    print(f"✗ [{i}/{len(tasks)}] {Path(pdf_path).name}{error_msg}")

    # Calculate statistics
    elapsed = time.time() - start_time
    rate = len(tasks) / elapsed if elapsed > 0 else 0

    if verbose:
        print()
        print("=" * 60)
        print(f"Conversion complete!")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Time: {elapsed:.2f} seconds")
        print(f"Rate: {rate:.2f} PDF/sec ({rate * 60:.0f} PDF/min)")
        print("=" * 60)

    return (successful, failed)


def convert_court_document(
    pdf_path: str,
    case_number: str,
    doc_type: str,
    output_base_dir: str = "documents"
) -> Optional[str]:
    """
    Convert court document PDF to Markdown with structured path.

    Creates path: output_base_dir/YYYY/case_number/doc_type.md

    Args:
        pdf_path: Path to PDF file
        case_number: Case number (e.g., "А40-12345-2024")
        doc_type: Document type (e.g., "решение_первая_инстанция")
        output_base_dir: Base directory for documents (default: "documents")

    Returns:
        Path to created MD file, or None if failed
    """
    try:
        # Extract year from case number
        parts = case_number.split("-")
        if len(parts) >= 3:
            year = parts[-1]
        else:
            year = "unknown"

        # Create structured path
        output_dir = Path(output_base_dir) / year / case_number
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate MD filename
        md_filename = f"{doc_type}.md"
        md_path = output_dir / md_filename

        # Convert
        success = convert_pdf_to_md(str(pdf_path), str(md_path), add_metadata=True)

        if success:
            return str(md_path)
        else:
            return None

    except Exception as e:
        print(f"Error converting court document {pdf_path}: {e}")
        return None


if __name__ == "__main__":
    # Example usage
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_to_md.py <pdf_file> [output_md_file]")
        print()
        print("Examples:")
        print("  python pdf_to_md.py document.pdf")
        print("  python pdf_to_md.py document.pdf output.md")
        sys.exit(1)

    pdf_file = sys.argv[1]
    md_file = sys.argv[2] if len(sys.argv) > 2 else Path(pdf_file).stem + ".md"

    print(f"Converting {pdf_file} to {md_file}...")

    success = convert_pdf_to_md(pdf_file, md_file)

    if success:
        print(f"✓ Successfully converted to {md_file}")
        # Show file size
        md_size = Path(md_file).stat().st_size
        print(f"  Size: {md_size:,} bytes")
    else:
        print(f"✗ Conversion failed")
        sys.exit(1)
