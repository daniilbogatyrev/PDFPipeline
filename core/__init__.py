"""
DocIntel Core Package.
"""

from .identifier import FileIdentifier
from .inspector import PDFInspector
from .orchestrator import DocumentOrchestrator
from .extractors import (
    PyMuPDFExtractor,
    PDFPlumberExtractor,
    get_default_extractor,
    get_available_extractors
)

__all__ = [
    "FileIdentifier",
    "PDFInspector",
    "DocumentOrchestrator",
    "PyMuPDFExtractor",
    "PDFPlumberExtractor",
    "get_default_extractor",
    "get_available_extractors",
]
