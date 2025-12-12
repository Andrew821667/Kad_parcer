#!/usr/bin/env python3
"""
Download court documents for a specific case.

Usage:
    python scripts/download_case_documents.py <case_number>
    python scripts/download_case_documents.py А40-12345-2024

Features:
- Connects to Chrome via CDP (http://localhost:9222)
- Downloads only important documents (Решение, Постановление, etc.)
- Rate limiting: 5 sec between requests
- Auto-retry on failures (3 attempts)
- Saves to downloads/YYYY/case_number/
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraper.playwright_scraper import PlaywrightScraper
from src.downloader import DocumentDownloader


async def download_case(case_number: str):
    """
    Download documents for a case.

    Args:
        case_number: Case number (e.g., "А40-12345-2024")
    """
    print(f"Downloading documents for case: {case_number}")
    print("=" * 60)
    print()

    # Connect to Chrome via CDP
    print("Connecting to Chrome (CDP: http://localhost:9222)...")

    try:
        async with PlaywrightScraper(use_cdp=True, cdp_url="http://localhost:9222") as scraper:
            print("✓ Connected to Chrome")
            print()

            # Create downloader
            downloader = DocumentDownloader(
                scraper,
                download_dir="downloads",
                rate_limit_delay=5.0  # 5 sec between requests
            )

            # Download documents
            print(f"Navigating to case {case_number}...")
            result = await downloader.download_case_documents(
                case_number,
                filter_important=True  # Only important documents
            )

            # Display results
            print()
            print("=" * 60)
            print("DOWNLOAD COMPLETE")
            print("=" * 60)
            print(f"Total documents found: {result['total']}")
            print(f"Important documents: {result['filtered']}")
            print(f"Successfully downloaded: {result['downloaded']}")
            print(f"Failed: {result['failed']}")
            print()

            if result['documents']:
                print("Downloaded files:")
                for doc in result['documents']:
                    print(f"  - {doc['filename']}")
                    print(f"    Type: {doc['doc_type']}")
                    print(f"    Path: {doc['local_path']}")
                    print()

            if result['downloaded'] > 0:
                # Show directory structure
                parts = case_number.split("-")
                year = parts[-1] if len(parts) >= 3 else "unknown"
                output_dir = Path("downloads") / year / case_number

                print(f"Documents saved to: {output_dir}")

            return result['downloaded'] > 0

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/download_case_documents.py <case_number>")
        print()
        print("Examples:")
        print("  python scripts/download_case_documents.py А40-12345-2024")
        print("  python scripts/download_case_documents.py А50-67890-2023")
        print()
        print("Requirements:")
        print("  - Chrome must be running with CDP enabled:")
        print("    google-chrome --remote-debugging-port=9222")
        sys.exit(1)

    case_number = sys.argv[1]

    # Run async download
    success = asyncio.run(download_case(case_number))

    if success:
        print("✓ Download completed successfully")
        sys.exit(0)
    else:
        print("✗ Download failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
