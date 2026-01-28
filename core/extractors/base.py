"""
Base Extractor Interface.
Erweitert um detaillierte Tabellen-Informationen und CSV-Extraktion.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union, List, Any
import time

# Optional pandas import
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


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
        data: Rohdaten der Tabelle (Liste von Listen)
        dataframe: Pandas DataFrame (falls extrahiert)
        header_row: Index der Header-Zeile (0-basiert), None wenn kein Header
    """
    table_id: int
    page: int
    rows: int = 0
    cols: int = 0
    bbox: tuple = field(default_factory=tuple)
    is_continuation: bool = False
    continues_to_page: Optional[int] = None
    
    # NEU: Tabellen-Daten
    data: List[List[Any]] = field(default_factory=list)
    dataframe: Optional[Any] = None  # pandas.DataFrame
    header_row: Optional[int] = None  # 0 = erste Zeile ist Header
    
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
    
    @property
    def has_data(self) -> bool:
        """Ob Tabellen-Daten extrahiert wurden."""
        return len(self.data) > 0 or self.dataframe is not None
    
    def to_dataframe(self, use_header: bool = True) -> "pd.DataFrame":
        """
        Konvertiert die Tabelle zu einem Pandas DataFrame.
        
        Args:
            use_header: Wenn True und header_row gesetzt, wird diese als Header verwendet
            
        Returns:
            pandas.DataFrame
        """
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas ist nicht installiert")
        
        # Falls bereits ein DataFrame existiert
        if self.dataframe is not None:
            return self.dataframe
        
        if not self.data:
            return pd.DataFrame()
        
        # Erstelle DataFrame aus Rohdaten
        if use_header and self.header_row is not None and len(self.data) > self.header_row:
            header = self.data[self.header_row]
            data_rows = self.data[self.header_row + 1:]
            df = pd.DataFrame(data_rows, columns=header)
        else:
            df = pd.DataFrame(self.data)
        
        return df
    
    def to_csv(self, use_header: bool = True, **kwargs) -> str:
        """
        Exportiert die Tabelle als CSV-String.
        
        Args:
            use_header: Wenn True, wird Header-Zeile inkludiert
            **kwargs: Weitere Argumente für pandas.to_csv()
            
        Returns:
            CSV als String
        """
        df = self.to_dataframe(use_header=use_header)
        
        # Standard CSV-Optionen
        csv_kwargs = {
            "index": False,
            "encoding": "utf-8",
        }
        csv_kwargs.update(kwargs)
        
        return df.to_csv(**csv_kwargs)
    
    def to_dict(self) -> dict:
        return {
            "table_id": self.table_id,
            "page": self.page,
            "rows": self.rows,
            "cols": self.cols,
            "bbox": self.bbox,
            "is_continuation": self.is_continuation,
            "continues_to_page": self.continues_to_page,
            "page_range": self.page_range_str,
            "has_data": self.has_data,
            "header_row": self.header_row
        }


@dataclass 
class CSVExtractionResult:
    """
    Ergebnis einer CSV-Extraktion für Benchmark-Vergleiche.
    
    Attributes:
        table_id: ID der Tabelle
        tool_name: Name des Extraktors
        dataframe: Extrahierte Daten als DataFrame
        rows: Anzahl Zeilen (ohne Header)
        cols: Anzahl Spalten
        header_detected: Ob ein Header erkannt wurde
        empty_cells: Anzahl leerer Zellen
        execution_time_ms: Extraktionszeit
        error: Fehlermeldung falls fehlgeschlagen
    """
    table_id: int
    tool_name: str
    dataframe: Optional[Any] = None  # pandas.DataFrame
    rows: int = 0
    cols: int = 0
    header_detected: bool = False
    empty_cells: int = 0
    merged_cells_detected: int = 0
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    
    @property
    def success(self) -> bool:
        return self.error is None and self.dataframe is not None
    
    @property
    def cell_count(self) -> int:
        return self.rows * self.cols
    
    @property
    def empty_cell_ratio(self) -> float:
        if self.cell_count == 0:
            return 0.0
        return self.empty_cells / self.cell_count
    
    def to_csv(self, **kwargs) -> str:
        """Exportiert als CSV-String."""
        if self.dataframe is None:
            return ""
        
        csv_kwargs = {"index": False, "encoding": "utf-8"}
        csv_kwargs.update(kwargs)
        return self.dataframe.to_csv(**csv_kwargs)
    
    def to_dict(self) -> dict:
        return {
            "table_id": self.table_id,
            "tool": self.tool_name,
            "rows": self.rows,
            "cols": self.cols,
            "cells": self.cell_count,
            "empty_cells": self.empty_cells,
            "empty_ratio": f"{self.empty_cell_ratio:.1%}",
            "header": "✓" if self.header_detected else "✗",
            "time_ms": round(self.execution_time_ms, 1),
            "status": "✓" if self.success else "✗"
        }


@dataclass
class ExtractionResult:
    """
    Einheitliches Ergebnis für alle Extraktoren.
    Erweitert um strukturierte Tabellen-Liste und CSV-Support.
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
    def tables_with_data(self) -> List[ExtractedTable]:
        """Nur Tabellen die auch Daten enthalten."""
        return [t for t in self.tables if t.has_data and not t.is_continuation]
    
    @property
    def tables_by_page(self) -> dict[int, List[ExtractedTable]]:
        """Gruppiert Tabellen nach Startseite."""
        result = {}
        for table in self.tables:
            if not table.is_continuation:
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
        
        main_tables = [t for t in self.tables if not t.is_continuation]
        parts = [f"T{t.table_id}({t.page_range_str})" for t in main_tables]
        return f"{len(main_tables)} Tabellen: {', '.join(parts)}"
    
    def get_table_by_id(self, table_id: int) -> Optional[ExtractedTable]:
        """Findet eine Tabelle nach ID."""
        for table in self.tables:
            if table.table_id == table_id and not table.is_continuation:
                return table
        return None
    
    def export_all_tables_to_csv(self) -> dict[int, str]:
        """
        Exportiert alle Tabellen als CSV.
        
        Returns:
            Dict mit table_id -> CSV-String
        """
        result = {}
        for table in self.tables:
            if not table.is_continuation and table.has_data:
                try:
                    result[table.table_id] = table.to_csv()
                except Exception as e:
                    result[table.table_id] = f"# Error: {e}"
        return result
    
    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "tables": self.table_count,
            "tables_with_data": len(self.tables_with_data),
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
            "Mit Daten": len(self.tables_with_data),
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
    
    def extract_table_to_csv(
        self, 
        source: Union[Path, bytes], 
        table_id: int,
        filename: str = ""
    ) -> CSVExtractionResult:
        """
        Extrahiert eine spezifische Tabelle als CSV.
        
        Args:
            source: PDF Quelle
            table_id: ID der Tabelle (1-basiert)
            filename: Optionaler Dateiname
            
        Returns:
            CSVExtractionResult
        """
        start = time.perf_counter()
        
        try:
            # Erst normale Extraktion
            extraction = self.extract(source, filename)
            
            if not extraction.success:
                return CSVExtractionResult(
                    table_id=table_id,
                    tool_name=self.name,
                    error=extraction.error,
                    execution_time_ms=(time.perf_counter() - start) * 1000
                )
            
            # Finde die Tabelle
            table = extraction.get_table_by_id(table_id)
            
            if not table:
                return CSVExtractionResult(
                    table_id=table_id,
                    tool_name=self.name,
                    error=f"Tabelle {table_id} nicht gefunden",
                    execution_time_ms=(time.perf_counter() - start) * 1000
                )
            
            if not table.has_data:
                return CSVExtractionResult(
                    table_id=table_id,
                    tool_name=self.name,
                    error=f"Tabelle {table_id} hat keine Daten",
                    execution_time_ms=(time.perf_counter() - start) * 1000
                )
            
            # Konvertiere zu DataFrame
            df = table.to_dataframe()
            
            # Zähle leere Zellen
            empty_cells = df.isna().sum().sum() + (df == "").sum().sum()
            
            return CSVExtractionResult(
                table_id=table_id,
                tool_name=self.name,
                dataframe=df,
                rows=len(df),
                cols=len(df.columns),
                header_detected=table.header_row is not None,
                empty_cells=int(empty_cells),
                execution_time_ms=(time.perf_counter() - start) * 1000
            )
            
        except Exception as e:
            return CSVExtractionResult(
                table_id=table_id,
                tool_name=self.name,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start) * 1000
            )
    
    def supports_page_info(self) -> bool:
        """Ob der Extractor Seiten-Informationen pro Tabelle liefert."""
        return True
    
    def supports_continuation_detection(self) -> bool:
        """Ob der Extractor spanning Tables erkennen kann."""
        return False
    
    def supports_csv_extraction(self) -> bool:
        """Ob der Extractor Tabellen-Daten als CSV extrahieren kann."""
        return False
