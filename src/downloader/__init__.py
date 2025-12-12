"""
Document downloader module for КАД Арбитр cases.

Downloads important court documents (PDFs) from case pages.
"""

from .document_downloader import (
    DocumentDownloader,
    IMPORTANT_DOCUMENT_TYPES,
    filter_important_documents,
)

__all__ = [
    "DocumentDownloader",
    "IMPORTANT_DOCUMENT_TYPES",
    "filter_important_documents",
]
