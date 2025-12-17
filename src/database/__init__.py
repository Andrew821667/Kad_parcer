"""
Database module for КАД Арбитр parser.

Manages SQLite database for case metadata and document references.
"""

from .sqlite_manager import SQLiteManager

__all__ = ["SQLiteManager"]
