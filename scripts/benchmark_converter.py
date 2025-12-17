#!/usr/bin/env python3
"""
Benchmark PDF to MD converter performance.
"""

import sys
import shutil
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.converter import batch_convert


def benchmark_converter(num_files: int = 100, num_workers: int = 4):
    """
    Benchmark converter with multiple PDF files.

    Args:
        num_files: Number of test PDFs to create
        num_workers: Number of parallel workers
    """
    # Get test PDF
    test_pdf = Path(__file__).parent.parent / "tests" / "data" / "test_document.pdf"

    if not test_pdf.exists():
        print(f"Error: Test PDF not found at {test_pdf}")
        print("Run: python scripts/create_test_pdf.py first")
        return

    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir)

    try:
        # Create copies of test PDF
        print(f"Creating {num_files} test PDF files...")
        pdf_files = []

        for i in range(num_files):
            pdf_copy = temp_path / f"test_{i:04d}.pdf"
            shutil.copy(test_pdf, pdf_copy)
            pdf_files.append(str(pdf_copy))

        print(f"✓ Created {len(pdf_files)} PDF files")
        print()

        # Benchmark conversion
        print(f"Benchmarking with {num_workers} workers...")
        print("=" * 60)

        output_dir = temp_path / "output"
        successful, failed = batch_convert(
            pdf_files,
            str(output_dir),
            num_workers=num_workers,
            verbose=True
        )

        print()
        print("=" * 60)
        print("BENCHMARK COMPLETE")
        print("=" * 60)
        print(f"Total files: {num_files}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Workers: {num_workers}")

    finally:
        # Cleanup
        shutil.rmtree(temp_dir)
        print(f"\n✓ Cleaned up temporary files")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark PDF to MD converter")
    parser.add_argument(
        "-n", "--num-files",
        type=int,
        default=100,
        help="Number of test PDF files (default: 100)"
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)"
    )

    args = parser.parse_args()

    benchmark_converter(args.num_files, args.workers)
