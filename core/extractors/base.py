"""
Base Extractor Interface.
Erweitert um detaillierte Tabellen-Informationen pro Seite.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union, List
import time


@dataclass
class ExtractedTable:
    """
    Detaillierte Information zu einer extrahierten Tabelle.
    
    Attributes:
        table_id: Laufende Nummer (1-basiert)
        page: Seite auf der die Tabelle beginnt (1-basiert)
        rows: Anzahl Zeilen
        cols: Anzahl Spalten
        bbox: Bounding Box (x0, y0, x1, y1) falls verfügbar
        is_continuation: True wenn Fortsetzung einer vorherigen Tabelle
        continues_to_page: Falls spanning, bis zu welcher Seite
    """
    table_id: int
    page: int
    rows: int = 0
    cols: int = 0
    bbox: tuple = field(default_factory=tuple)
    is_continuation: bool = False
    continues_to_page: Optional[int] = None
    
    @property
    def is_spanning(self) -> bool:
        """Tabelle geht über mehrere Seiten."""
        return self.continues_to_page is not None and self.continues_to_page > self.page
    
    @property
    def page_range(self) -> tuple[int, int]:
        """(start_page, end_page) der Tabelle."""
        end = self.continues_to_page if self.continues_to_page else self.page
        return (self.page, end)
    
    @property
    def page_range_str(self) -> str:
        """Menschenlesbare Seiten-Angabe."""
        start, end = self.page_range
        if start == end:
            return f"S.{start}"
        return f"S.{start}-{end}"
    
    def to_dict(self) -> dict:
        return {
            "table_id": self.table_id,
            "page": self.page,
            "rows": self.rows,
            "cols": self.cols,
            "bbox": self.bbox,
            "is_continuation": self.is_continuation,
            "continues_to_page": self.continues_to_page,
            "page_range": self.page_range_str
        }


@dataclass
class ExtractionResult:
    """
    Einheitliches Ergebnis für alle Extraktoren.
    Erweitert um strukturierte Tabellen-Liste.
    """
    tool_name: str
    file_path: str
    table_count: int = 0
    tables: List[ExtractedTable] = field(default_factory=list)
    image_count: int = 0
    image_count_total: int = 0
    pages: int = 0
    paragraphs: int = 0
    math_formulas: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    
    # Legacy: tables_data für Abwärtskompatibilität
    tables_data: list = field(default_factory=list)
    
    @property
    def success(self) -> bool:
        return self.error is None
    
    @property
    def spanning_table_count(self) -> int:
        """Anzahl der Tabellen die über mehrere Seiten gehen."""
        return sum(1 for t in self.tables if t.is_spanning)
    
    @property
    def tables_by_page(self) -> dict[int, List[ExtractedTable]]:
        """Gruppiert Tabellen nach Startseite."""
        result = {}
        for table in self.tables:
            if not table.is_continuation:  # Nur Haupt-Tabellen, nicht Fortsetzungen
                page = table.page
                if page not in result:
                    result[page] = []
                result[page].append(table)
        return result
    
    @property
    def pages_with_tables(self) -> List[int]:
        """Sortierte Liste aller Seiten mit Tabellen."""
        pages = set()
        for table in self.tables:
            if not table.is_continuation:
                start, end = table.page_range
                for p in range(start, end + 1):
                    pages.add(p)
        return sorted(pages)
    
    def get_table_summary(self) -> str:
        """
        Erzeugt eine Zusammenfassung wie:
        "4 Tabellen: T1(S.1-4), T2(S.5), T3(S.6), T4(S.6)"
        """
        if not self.tables:
            return f"{self.table_count} Tabellen (keine Details)"
        
        # Filtere Fortsetzungen raus
        main_tables = [t for t in self.tables if not t.is_continuation]
        
        parts = [f"T{t.table_id}({t.page_range_str})" for t in main_tables]
        return f"{len(main_tables)} Tabellen: {', '.join(parts)}"
    
    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "tables": self.table_count,
            "tables_detail": [t.to_dict() for t in self.tables],
            "tables_summary": self.get_table_summary(),
            "spanning_tables": self.spanning_table_count,
            "pages_with_tables": self.pages_with_tables,
            "images": self.image_count,
            "images_total": self.image_count_total,
            "pages": self.pages,
            "paragraphs": self.paragraphs,
            "math_formulas": self.math_formulas,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }
    
    def to_summary_dict(self) -> dict:
        """Kompakte Zusammenfassung für DataFrame."""
        return {
            "Tool": self.tool_name,
            "Tabellen": self.table_count,
            "Spanning": self.spanning_table_count,
            "Seiten m. Tab.": len(self.pages_with_tables),
            "Bilder": self.image_count,
            "Zeit (ms)": round(self.execution_time_ms, 1)
        }


class BaseExtractor(ABC):
    """Abstrakte Basisklasse für PDF-Extraktoren."""
    
    def __init__(self):
        self._name = self.__class__.__name__
    
    @property
    def name(self) -> str:
        return self._name
    
    @abstractmethod
    def is_available(self) -> bool:
        """Prüft ob die benötigten Libraries installiert sind."""
        pass
    
    @abstractmethod
    def extract(self, source: Union[Path, bytes], filename: str = "") -> ExtractionResult:
        """
        Extrahiert Informationen aus einem PDF.
        
        Args:
            source: Pfad zur Datei oder Bytes
            filename: Optionaler Dateiname für Reporting
            
        Returns:
            ExtractionResult mit allen gefundenen Elementen
        """
        pass
    
    def supports_page_info(self) -> bool:
        """Ob der Extractor Seiten-Informationen pro Tabelle liefert."""
        return True
    
    def supports_continuation_detection(self) -> bool:
        """Ob der Extractor spanning Tables erkennen kann."""
        return False
