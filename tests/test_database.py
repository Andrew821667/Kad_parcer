#!/usr/bin/env python3
"""
Unit tests for SQLiteManager (database module).
"""

import unittest
import tempfile
import os
from pathlib import Path
import json

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import SQLiteManager


class TestSQLiteManager(unittest.TestCase):
    """Test cases for SQLiteManager class."""

    def setUp(self):
        """Set up test database before each test."""
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name

        # Initialize database
        self.db = SQLiteManager(self.db_path)

    def tearDown(self):
        """Clean up after each test."""
        # Close database
        self.db.close()

        # Remove temp file
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_database_creation(self):
        """Test that database file is created."""
        self.assertTrue(os.path.exists(self.db_path))
        self.assertIsNotNone(self.db.conn)

    def test_schema_creation(self):
        """Test that tables are created."""
        cursor = self.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}

        self.assertIn('cases', tables)
        self.assertIn('documents', tables)

    def test_indexes_creation(self):
        """Test that indexes are created."""
        cursor = self.db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        indexes = {row[0] for row in cursor.fetchall()}

        self.assertIn('idx_cases_year', indexes)
        self.assertIn('idx_cases_court', indexes)
        self.assertIn('idx_cases_registration_date', indexes)
        self.assertIn('idx_documents_case_number', indexes)
        self.assertIn('idx_documents_doc_type', indexes)

    def test_insert_case(self):
        """Test inserting a single case."""
        case_data = {
            "case_number": "А40-12345-2024",
            "court": "АС города Москвы",
            "registration_date": "2024-01-15",
            "year": 2024,
            "status": "В производстве",
            "parties": "ООО Компания vs ООО Контрагент"
        }

        result = self.db.insert_case(case_data)
        self.assertTrue(result)

        # Check if case exists
        self.assertTrue(self.db.case_exists("А40-12345-2024"))

    def test_insert_duplicate_case(self):
        """Test that duplicate cases are ignored."""
        case_data = {
            "case_number": "А40-12345-2024",
            "court": "АС города Москвы",
            "registration_date": "2024-01-15",
            "year": 2024,
        }

        # Insert first time
        result1 = self.db.insert_case(case_data)
        self.assertTrue(result1)

        # Insert second time (should be ignored)
        result2 = self.db.insert_case(case_data)
        self.assertTrue(result2)  # Returns True but doesn't duplicate

        # Check only one record exists
        stats = self.db.get_stats()
        self.assertEqual(stats['total_cases'], 1)

    def test_case_exists(self):
        """Test case_exists method."""
        # Non-existent case
        self.assertFalse(self.db.case_exists("А40-99999-2024"))

        # Insert case
        case_data = {
            "case_number": "А40-12345-2024",
            "court": "АС города Москвы",
        }
        self.db.insert_case(case_data)

        # Existing case
        self.assertTrue(self.db.case_exists("А40-12345-2024"))

    def test_update_case(self):
        """Test updating case data."""
        # Insert case
        case_data = {
            "case_number": "А40-12345-2024",
            "court": "АС города Москвы",
            "status": "В производстве",
        }
        self.db.insert_case(case_data)

        # Update status
        update_data = {
            "status": "Рассмотрено",
        }
        result = self.db.update_case("А40-12345-2024", update_data)
        self.assertTrue(result)

        # Verify update
        cases = self.db.get_cases_by_year(2024)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['status'], "Рассмотрено")

    def test_insert_document(self):
        """Test inserting a document."""
        # Insert case first
        case_data = {
            "case_number": "А40-12345-2024",
            "court": "АС города Москвы",
        }
        self.db.insert_case(case_data)

        # Insert document
        doc_data = {
            "case_number": "А40-12345-2024",
            "doc_type": "Решение",
            "instance": "Первая инстанция",
            "is_final": 1,
            "md_path": "documents/2024/А40-12345-2024/решение.md",
            "file_size": 51200,
        }

        doc_id = self.db.insert_document(doc_data)
        self.assertIsNotNone(doc_id)
        self.assertIsInstance(doc_id, int)

    def test_get_case_documents(self):
        """Test retrieving documents for a case."""
        # Insert case
        case_data = {
            "case_number": "А40-12345-2024",
            "court": "АС города Москвы",
        }
        self.db.insert_case(case_data)

        # Insert multiple documents
        for i, doc_type in enumerate(["Решение", "Постановление", "Определение"]):
            doc_data = {
                "case_number": "А40-12345-2024",
                "doc_type": doc_type,
                "instance": f"Инстанция {i+1}",
                "md_path": f"documents/2024/А40-12345-2024/{doc_type}.md",
            }
            self.db.insert_document(doc_data)

        # Get documents
        documents = self.db.get_case_documents("А40-12345-2024")
        self.assertEqual(len(documents), 3)
        self.assertEqual(documents[0]['doc_type'], "Решение")
        self.assertEqual(documents[1]['doc_type'], "Постановление")
        self.assertEqual(documents[2]['doc_type'], "Определение")

    def test_get_cases_by_year(self):
        """Test filtering cases by year."""
        # Insert cases for different years
        for year in [2022, 2023, 2024]:
            for i in range(3):
                case_data = {
                    "case_number": f"А40-{year}-{i:05d}",
                    "court": "АС города Москвы",
                    "registration_date": f"{year}-01-15",
                    "year": year,
                }
                self.db.insert_case(case_data)

        # Get 2024 cases
        cases_2024 = self.db.get_cases_by_year(2024)
        self.assertEqual(len(cases_2024), 3)
        for case in cases_2024:
            self.assertEqual(case['year'], 2024)

        # Get 2023 cases
        cases_2023 = self.db.get_cases_by_year(2023)
        self.assertEqual(len(cases_2023), 3)

    def test_get_stats(self):
        """Test statistics generation."""
        # Insert test data
        for year in [2023, 2024]:
            for i in range(5):
                case_data = {
                    "case_number": f"А40-{year}-{i:05d}",
                    "court": f"Суд {i % 2}",
                    "year": year,
                }
                self.db.insert_case(case_data)

                # Add documents
                for j in range(2):
                    doc_data = {
                        "case_number": f"А40-{year}-{i:05d}",
                        "doc_type": "Решение" if j == 0 else "Постановление",
                        "md_path": f"documents/{year}/doc_{i}_{j}.md",
                    }
                    self.db.insert_document(doc_data)

        # Get stats
        stats = self.db.get_stats()

        self.assertEqual(stats['total_cases'], 10)
        self.assertEqual(stats['total_documents'], 20)
        self.assertEqual(stats['cases_by_year'][2024], 5)
        self.assertEqual(stats['cases_by_year'][2023], 5)
        self.assertIn('Решение', stats['documents_by_type'])
        self.assertIn('Постановление', stats['documents_by_type'])

    def test_bulk_insert_cases(self):
        """Test bulk inserting multiple cases."""
        cases = [
            {
                "case_number": f"А40-2024-{i:05d}",
                "court": "АС города Москвы",
                "registration_date": "2024-01-15",
                "year": 2024,
            }
            for i in range(100)
        ]

        inserted = self.db.bulk_insert_cases(cases)
        self.assertEqual(inserted, 100)

        stats = self.db.get_stats()
        self.assertEqual(stats['total_cases'], 100)

    def test_bulk_insert_with_duplicates(self):
        """Test bulk insert ignores duplicates."""
        cases = [
            {"case_number": "А40-2024-00001", "court": "Суд 1"},
            {"case_number": "А40-2024-00002", "court": "Суд 2"},
            {"case_number": "А40-2024-00001", "court": "Суд 1"},  # Duplicate
        ]

        inserted = self.db.bulk_insert_cases(cases)
        self.assertEqual(inserted, 2)  # Only 2 unique cases

        stats = self.db.get_stats()
        self.assertEqual(stats['total_cases'], 2)

    def test_import_from_json(self):
        """Test importing cases from JSON file."""
        # Create temporary JSON file
        json_data = [
            {
                "case_number": "А40-12345-2024",
                "court": "АС города Москвы",
                "registration_date": "2024-01-15",
                "year": 2024,
            },
            {
                "case_number": "А40-12346-2024",
                "court": "АС Московской области",
                "registration_date": "2024-01-16",
                "year": 2024,
            }
        ]

        temp_json = tempfile.NamedTemporaryFile(
            mode='w', delete=False, suffix='.json', encoding='utf-8'
        )
        json.dump(json_data, temp_json, ensure_ascii=False)
        temp_json.close()

        try:
            # Import from JSON
            imported = self.db.import_from_json(temp_json.name)
            self.assertEqual(imported, 2)

            stats = self.db.get_stats()
            self.assertEqual(stats['total_cases'], 2)

        finally:
            # Clean up
            os.remove(temp_json.name)

    def test_context_manager(self):
        """Test using SQLiteManager as context manager."""
        with SQLiteManager(self.db_path) as db:
            case_data = {
                "case_number": "А40-12345-2024",
                "court": "АС города Москвы",
            }
            db.insert_case(case_data)

        # Connection should be closed
        # Re-open to verify data was saved
        with SQLiteManager(self.db_path) as db:
            self.assertTrue(db.case_exists("А40-12345-2024"))

    def test_year_extraction_from_date(self):
        """Test automatic year extraction from registration_date."""
        case_data = {
            "case_number": "А40-12345-2024",
            "court": "АС города Москвы",
            "registration_date": "2024-06-15",
            # year not provided - should be extracted
        }

        self.db.insert_case(case_data)

        cases = self.db.get_cases_by_year(2024)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]['year'], 2024)


class TestSQLiteManagerEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.db = SQLiteManager(self.db_path)

    def tearDown(self):
        """Clean up."""
        self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_insert_case_without_case_number(self):
        """Test inserting case without required case_number."""
        case_data = {
            "court": "АС города Москвы",
            # case_number missing
        }

        result = self.db.insert_case(case_data)
        self.assertFalse(result)

    def test_update_nonexistent_case(self):
        """Test updating a case that doesn't exist."""
        update_data = {
            "status": "Новый статус",
        }

        result = self.db.update_case("А40-99999-2024", update_data)
        self.assertFalse(result)

    def test_import_nonexistent_json(self):
        """Test importing from non-existent JSON file."""
        imported = self.db.import_from_json("nonexistent_file.json")
        self.assertEqual(imported, 0)


def run_tests():
    """Run all tests."""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
