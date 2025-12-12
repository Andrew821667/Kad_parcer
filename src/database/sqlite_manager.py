#!/usr/bin/env python3
"""
SQLite manager for КАД Арбитр case metadata database.

Manages case metadata and document references with optimizations for large-scale data.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import json


class SQLiteManager:
    """
    Manager for SQLite database with КАД Арбитр case metadata.

    Features:
    - Optimized PRAGMA settings (WAL mode, large cache, mmap)
    - Two tables: cases (metadata) and documents (references to MD files)
    - Deduplication via case_number PRIMARY KEY
    - Indexes for fast queries by year, court, date
    """

    def __init__(self, db_path: str = "data/kad_2024.db"):
        """
        Initialize SQLite database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._create_schema()
        self._optimize_pragmas()

    def _connect(self) -> None:
        """Establish database connection."""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row  # Enable column access by name

    def _optimize_pragmas(self) -> None:
        """
        Apply PRAGMA optimizations for performance.

        Optimizations:
        - WAL mode: Better concurrency and performance
        - cache_size: 64MB cache in memory
        - mmap_size: 1GB memory-mapped I/O
        - synchronous: NORMAL for better write performance
        - temp_store: MEMORY for temp tables in RAM
        """
        if not self.conn:
            return

        pragmas = [
            "PRAGMA journal_mode = WAL",           # Write-Ahead Logging
            "PRAGMA cache_size = -64000",          # 64 MB cache (negative = KB)
            "PRAGMA mmap_size = 1073741824",       # 1 GB mmap
            "PRAGMA synchronous = NORMAL",         # Balance safety/speed
            "PRAGMA temp_store = MEMORY",          # Temp tables in RAM
            "PRAGMA foreign_keys = ON",            # Enforce foreign keys
        ]

        for pragma in pragmas:
            self.conn.execute(pragma)

        self.conn.commit()

    def _create_schema(self) -> None:
        """
        Create database schema with tables and indexes.

        Tables:
        - cases: Case metadata (case_number PK, court, date, parties, etc.)
        - documents: Document references (id PK, case_number FK, type, MD path, etc.)

        Indexes:
        - cases: year, court, registration_date for fast filtering
        - documents: case_number, doc_type for fast lookups
        """
        if not self.conn:
            return

        # Create cases table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                case_number TEXT PRIMARY KEY,
                court TEXT,
                registration_date DATE,
                year INTEGER,
                status TEXT,
                parties TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create documents table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_number TEXT NOT NULL,
                doc_type TEXT,
                instance TEXT,
                is_final BOOLEAN DEFAULT 0,
                pdf_url TEXT,
                md_path TEXT,
                parsed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                file_size INTEGER,
                FOREIGN KEY (case_number) REFERENCES cases(case_number)
                    ON DELETE CASCADE
            )
        """)

        # Create indexes for fast queries
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cases_year
            ON cases(year)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cases_court
            ON cases(court)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cases_registration_date
            ON cases(registration_date)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_case_number
            ON documents(case_number)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_doc_type
            ON documents(doc_type)
        """)

        self.conn.commit()

    def insert_case(self, case_data: Dict[str, Any]) -> bool:
        """
        Insert new case into database.

        Args:
            case_data: Dictionary with case fields:
                - case_number (required): Case number (e.g., "А40-12345-2024")
                - court: Court name
                - registration_date: Registration date (YYYY-MM-DD)
                - year: Year (extracted from case_number or date)
                - status: Case status
                - parties: Parties involved (JSON string or text)

        Returns:
            True if inserted, False if already exists or error
        """
        if not self.conn:
            return False

        # Check required fields
        if "case_number" not in case_data:
            return False

        # Extract year if not provided
        if "year" not in case_data:
            # Try to extract from registration_date first
            if "registration_date" in case_data:
                try:
                    date_str = case_data["registration_date"]
                    year = int(date_str.split("-")[0])
                    case_data["year"] = year
                except (ValueError, IndexError):
                    pass
            # If still no year, try to extract from case_number (А40-12345-2024)
            if "year" not in case_data and "case_number" in case_data:
                try:
                    case_number = case_data["case_number"]
                    # Extract last part after last dash
                    parts = case_number.split("-")
                    if len(parts) >= 3:
                        potential_year = int(parts[-1])
                        # Validate it's a reasonable year (2000-2099)
                        if 2000 <= potential_year <= 2099:
                            case_data["year"] = potential_year
                except (ValueError, IndexError):
                    pass

        try:
            # Use INSERT OR IGNORE to skip duplicates
            # Extract values with .get() to handle missing fields
            self.conn.execute("""
                INSERT OR IGNORE INTO cases
                (case_number, court, registration_date, year, status, parties)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                case_data.get('case_number'),
                case_data.get('court'),
                case_data.get('registration_date'),
                case_data.get('year'),
                case_data.get('status'),
                case_data.get('parties'),
            ))

            self.conn.commit()
            return True

        except sqlite3.Error as e:
            print(f"Error inserting case {case_data.get('case_number')}: {e}")
            return False

    def case_exists(self, case_number: str) -> bool:
        """
        Check if case exists in database.

        Args:
            case_number: Case number to check

        Returns:
            True if exists, False otherwise
        """
        if not self.conn:
            return False

        cursor = self.conn.execute(
            "SELECT 1 FROM cases WHERE case_number = ? LIMIT 1",
            (case_number,)
        )

        return cursor.fetchone() is not None

    def update_case(self, case_number: str, data: Dict[str, Any]) -> bool:
        """
        Update existing case data.

        Args:
            case_number: Case number to update
            data: Dictionary with fields to update

        Returns:
            True if updated, False if not found or error
        """
        if not self.conn or not data:
            return False

        # Build UPDATE query dynamically
        fields = []
        values = []

        for key, value in data.items():
            if key != "case_number":  # Don't update primary key
                fields.append(f"{key} = ?")
                values.append(value)

        if not fields:
            return False

        # Add updated_at timestamp
        fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())

        # Add case_number to WHERE clause
        values.append(case_number)

        try:
            query = f"UPDATE cases SET {', '.join(fields)} WHERE case_number = ?"
            cursor = self.conn.execute(query, values)
            self.conn.commit()

            return cursor.rowcount > 0

        except sqlite3.Error as e:
            print(f"Error updating case {case_number}: {e}")
            return False

    def insert_document(self, doc_data: Dict[str, Any]) -> Optional[int]:
        """
        Insert document reference into database.

        Args:
            doc_data: Dictionary with document fields:
                - case_number (required): Related case number
                - doc_type: Document type (e.g., "Решение", "Постановление")
                - instance: Instance level (e.g., "Первая инстанция")
                - is_final: Whether document is final (0/1)
                - pdf_url: Original PDF URL
                - md_path: Path to converted Markdown file
                - file_size: File size in bytes

        Returns:
            Document ID if inserted, None on error
        """
        if not self.conn:
            return None

        # Check required fields
        if "case_number" not in doc_data:
            return None

        try:
            cursor = self.conn.execute("""
                INSERT INTO documents
                (case_number, doc_type, instance, is_final, pdf_url, md_path, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_data.get('case_number'),
                doc_data.get('doc_type'),
                doc_data.get('instance'),
                doc_data.get('is_final', 0),  # Default to 0 if not specified
                doc_data.get('pdf_url'),
                doc_data.get('md_path'),
                doc_data.get('file_size'),
            ))

            self.conn.commit()
            return cursor.lastrowid

        except sqlite3.Error as e:
            print(f"Error inserting document for case {doc_data.get('case_number')}: {e}")
            return None

    def get_cases_by_year(self, year: int) -> List[Dict[str, Any]]:
        """
        Get all cases for a specific year.

        Args:
            year: Year to filter by

        Returns:
            List of case dictionaries
        """
        if not self.conn:
            return []

        cursor = self.conn.execute(
            "SELECT * FROM cases WHERE year = ? ORDER BY registration_date",
            (year,)
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_case_documents(self, case_number: str) -> List[Dict[str, Any]]:
        """
        Get all documents for a specific case.

        Args:
            case_number: Case number

        Returns:
            List of document dictionaries
        """
        if not self.conn:
            return []

        cursor = self.conn.execute(
            "SELECT * FROM documents WHERE case_number = ? ORDER BY id",
            (case_number,)
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with statistics:
            - total_cases: Total number of cases
            - total_documents: Total number of documents
            - cases_by_year: Cases grouped by year
            - documents_by_type: Documents grouped by type
        """
        if not self.conn:
            return {}

        stats = {}

        # Total cases
        cursor = self.conn.execute("SELECT COUNT(*) FROM cases")
        stats["total_cases"] = cursor.fetchone()[0]

        # Total documents
        cursor = self.conn.execute("SELECT COUNT(*) FROM documents")
        stats["total_documents"] = cursor.fetchone()[0]

        # Cases by year
        cursor = self.conn.execute("""
            SELECT year, COUNT(*) as count
            FROM cases
            WHERE year IS NOT NULL
            GROUP BY year
            ORDER BY year DESC
        """)
        stats["cases_by_year"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Documents by type
        cursor = self.conn.execute("""
            SELECT doc_type, COUNT(*) as count
            FROM documents
            WHERE doc_type IS NOT NULL
            GROUP BY doc_type
            ORDER BY count DESC
        """)
        stats["documents_by_type"] = {row[0]: row[1] for row in cursor.fetchall()}

        # Cases by court (top 10)
        cursor = self.conn.execute("""
            SELECT court, COUNT(*) as count
            FROM cases
            WHERE court IS NOT NULL
            GROUP BY court
            ORDER BY count DESC
            LIMIT 10
        """)
        stats["top_courts"] = {row[0]: row[1] for row in cursor.fetchall()}

        return stats

    def bulk_insert_cases(self, cases: List[Dict[str, Any]]) -> int:
        """
        Bulk insert multiple cases efficiently.

        Args:
            cases: List of case dictionaries

        Returns:
            Number of cases inserted (excluding duplicates)
        """
        if not self.conn or not cases:
            return 0

        inserted = 0

        try:
            for case_data in cases:
                # Extract year if not provided
                if "year" not in case_data:
                    # Try to extract from registration_date first
                    if "registration_date" in case_data:
                        try:
                            date_str = case_data["registration_date"]
                            year = int(date_str.split("-")[0])
                            case_data["year"] = year
                        except (ValueError, IndexError):
                            pass
                    # If still no year, try to extract from case_number
                    if "year" not in case_data and "case_number" in case_data:
                        try:
                            case_number = case_data["case_number"]
                            parts = case_number.split("-")
                            if len(parts) >= 3:
                                potential_year = int(parts[-1])
                                if 2000 <= potential_year <= 2099:
                                    case_data["year"] = potential_year
                        except (ValueError, IndexError):
                            pass

                cursor = self.conn.execute("""
                    INSERT OR IGNORE INTO cases
                    (case_number, court, registration_date, year, status, parties)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    case_data.get('case_number'),
                    case_data.get('court'),
                    case_data.get('registration_date'),
                    case_data.get('year'),
                    case_data.get('status'),
                    case_data.get('parties'),
                ))

                if cursor.rowcount > 0:
                    inserted += 1

            self.conn.commit()

        except sqlite3.Error as e:
            print(f"Error during bulk insert: {e}")
            self.conn.rollback()

        return inserted

    def import_from_json(self, json_path: str) -> int:
        """
        Import cases from JSON file (from parser output).

        Args:
            json_path: Path to JSON file with cases array

        Returns:
            Number of cases imported
        """
        json_file = Path(json_path)
        if not json_file.exists():
            print(f"JSON file not found: {json_path}")
            return 0

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Handle both array and object with 'cases' key
            if isinstance(data, list):
                cases = data
            elif isinstance(data, dict) and "cases" in data:
                cases = data["cases"]
            else:
                print(f"Invalid JSON format in {json_path}")
                return 0

            return self.bulk_insert_cases(cases)

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON file {json_path}: {e}")
            return 0
        except Exception as e:
            print(f"Error importing from {json_path}: {e}")
            return 0

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""
        self.close()

    def __del__(self):
        """Destructor - ensure connection is closed."""
        self.close()


if __name__ == "__main__":
    # Example usage
    with SQLiteManager("data/kad_2024.db") as db:
        # Insert test case
        test_case = {
            "case_number": "А40-12345-2024",
            "court": "АС города Москвы",
            "registration_date": "2024-01-15",
            "year": 2024,
            "status": "В производстве",
            "parties": "ООО Компания vs ООО Контрагент"
        }

        db.insert_case(test_case)

        # Insert test document
        test_doc = {
            "case_number": "А40-12345-2024",
            "doc_type": "Решение",
            "instance": "Первая инстанция",
            "is_final": 1,
            "md_path": "documents/2024/А40-12345-2024/решение_первая_инстанция.md",
            "file_size": 51200
        }

        db.insert_document(test_doc)

        # Print stats
        stats = db.get_stats()
        print(f"Total cases: {stats['total_cases']}")
        print(f"Total documents: {stats['total_documents']}")
