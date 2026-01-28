"""
PDF Extractors Package.
Enthält alle Extraktoren für Tabellen-Zählung und CSV-Extraktion.
"""

from .base import (
    BaseExtractor, 
    ExtractionResult, 
    ExtractedTable,
    CSVExtractionResult
)
from .pymupdf_extractors import PyMuPDFExtractor
from .pdf_plumber_extractor import PDFPlumberExtractor, PDFPlumberStreamExtractor
from .camelot_extractor import CamelotExtractor
from .tabula_extractor import TabulaExtractor


def get_default_extractor() -> PyMuPDFExtractor:
    """Standard-Extractor für die Pipeline (mit CSV-Support)."""
    return PyMuPDFExtractor(
        table_strategy="lines_strict",
        detect_continuations=True,
        deduplicate_images=True,
        extract_data=True
    )


def get_benchmark_extractors() -> list[BaseExtractor]:
    """Alle Extraktoren für Tabellen-Zählung Benchmark."""
    return [
        PyMuPDFExtractor(table_strategy="lines_strict", detect_continuations=True, extract_data=True),
        PyMuPDFExtractor(table_strategy="lines_strict", detect_continuations=False, extract_data=True),
        PyMuPDFExtractor(table_strategy="lines", detect_continuations=False, extract_data=True),
        PDFPlumberExtractor(extract_data=True),
        PDFPlumberStreamExtractor(extract_data=True),
        CamelotExtractor(flavor="lattice", extract_data=True),
        CamelotExtractor(flavor="stream", extract_data=True),
        TabulaExtractor(mode="lattice", extract_data=True),
        TabulaExtractor(mode="stream", extract_data=True),
    ]


def get_csv_extractors() -> list[BaseExtractor]:
    """Extraktoren die CSV-Extraktion unterstützen."""
    return [e for e in get_benchmark_extractors() if e.supports_csv_extraction()]


def get_available_extractors() -> list[BaseExtractor]:
    """Nur installierte Extraktoren."""
    return [e for e in get_benchmark_extractors() if e.is_available()]


def get_available_csv_extractors() -> list[BaseExtractor]:
    """Nur installierte Extraktoren mit CSV-Support."""
    return [e for e in get_available_extractors() if e.supports_csv_extraction()]


__all__ = [
    # Base Classes
    "BaseExtractor",
    "ExtractionResult",
    "ExtractedTable",
    "CSVExtractionResult",
    
    # Extractors
    "PyMuPDFExtractor",
    "PDFPlumberExtractor",
    "PDFPlumberStreamExtractor",
    "CamelotExtractor",
    "TabulaExtractor",
    
    # Factory Functions
    "get_default_extractor",
    "get_benchmark_extractors",
    "get_csv_extractors",
    "get_available_extractors",
    "get_available_csv_extractors",
]
