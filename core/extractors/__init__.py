"""
PDF Extractors Package.
"""

from .base import BaseExtractor, ExtractionResult
from .pymupdf_extractors import PyMuPDFExtractor
from .pdf_plumber_extractor import PDFPlumberExtractor
from .camelot_extractor import CamelotExtractor
from .tabula_extractor import TabulaExtractor



def get_default_extractor() -> PyMuPDFExtractor:
    """Standard-Extractor für die Pipeline."""
    return PyMuPDFExtractor(
        table_strategy="lines_strict",
        detect_continuations=True,
        deduplicate_images=True
    )


def get_benchmark_extractors() -> list[BaseExtractor]:
    """Alle Extraktoren für Benchmark."""
    return [
        PyMuPDFExtractor(table_strategy="lines_strict", detect_continuations=True),
        PyMuPDFExtractor(table_strategy="lines_strict", detect_continuations=False),
        PyMuPDFExtractor(table_strategy="lines", detect_continuations=False),
        PDFPlumberExtractor(),
        CamelotExtractor(flavor="lattice"),
        CamelotExtractor(flavor="stream"),
        TabulaExtractor(mode="lattice"),
        TabulaExtractor(mode="stream"),

    ]


def get_available_extractors() -> list[BaseExtractor]:
    """Nur installierte Extraktoren."""
    return [e for e in get_benchmark_extractors() if e.is_available()]


__all__ = [
    "BaseExtractor",
    "ExtractionResult",
    "PyMuPDFExtractor",
    "PDFPlumberExtractor",
    "get_default_extractor",
    "get_benchmark_extractors",
    "get_available_extractors",
    "CamelotExtractor",
    "TabulaExtractor",  
]
