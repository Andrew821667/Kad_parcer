#!/usr/bin/env python3
"""
Import parsed cases from JSON to SQLite database.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import SQLiteManager


def import_json_to_db(json_path: str, db_path: str = "data/kad_2024.db"):
    """
    Import cases from JSON file to SQLite database.

    Args:
        json_path: Path to JSON file with cases
        db_path: Path to SQLite database (default: data/kad_2024.db)
    """
    print(f"Importing cases from {json_path} to {db_path}...")
    print()

    with SQLiteManager(db_path) as db:
        # Import cases
        imported = db.import_from_json(json_path)

        print(f"✅ Imported {imported} cases")
        print()

        # Show statistics
        stats = db.get_stats()
        print("=" * 60)
        print("DATABASE STATISTICS")
        print("=" * 60)
        print(f"Total cases: {stats['total_cases']}")
        print(f"Total documents: {stats['total_documents']}")
        print()

        if stats['cases_by_year']:
            print("Cases by year:")
            for year, count in sorted(stats['cases_by_year'].items(), reverse=True):
                print(f"  {year}: {count:,}")
            print()

        if stats['top_courts']:
            print("Top 10 courts:")
            for court, count in list(stats['top_courts'].items())[:10]:
                print(f"  {court}: {count:,}")
            print()

        if stats['documents_by_type']:
            print("Documents by type:")
            for doc_type, count in stats['documents_by_type'].items():
                print(f"  {doc_type}: {count:,}")
            print()

        print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_json_to_db.py <json_file> [db_path]")
        print()
        print("Examples:")
        print("  python scripts/import_json_to_db.py data/january_2024_cases.json")
        print("  python scripts/import_json_to_db.py data/cases.json data/kad_2024.db")
        sys.exit(1)

    json_file = sys.argv[1]
    db_file = sys.argv[2] if len(sys.argv) > 2 else "data/kad_2024.db"

    import_json_to_db(json_file, db_file)
