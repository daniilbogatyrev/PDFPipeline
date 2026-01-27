"""
DocIntel Core Package.
"""

from .identifier import FileIdentifier
from .inspector import PDFInspector
from .orchestrator import DocumentOrchestrator
from .table_exporter import TableExporter, ExportedTable, create_table_export_summary
from .extractors import (
    PyMuPDFExtractor,
    PDFPlumberExtractor,
    ExtractedTable,
    get_default_extractor,
    get_available_extractors
)

__all__ = [
    "FileIdentifier",
    "PDFInspector",
    "DocumentOrchestrator",
    "TableExporter",
    "ExportedTable",
    "create_table_export_summary",
    "PyMuPDFExtractor",
    "PDFPlumberExtractor",
    "ExtractedTable",
    "get_default_extractor",
    "get_available_extractors",
]
