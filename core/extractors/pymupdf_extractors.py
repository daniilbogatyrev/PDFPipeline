"""
PyMuPDF Extractor.
Erweitert mit präziser Tabellen-Tracking und CSV-Extraktion.
"""

from pathlib import Path
from typing import Union, Optional, List, Any
import time
import re

from .base import BaseExtractor, ExtractionResult, ExtractedTable, CSVExtractionResult

# Optional pandas
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class PyMuPDFExtractor(BaseExtractor):
    """
    Extractor basierend auf PyMuPDF (fitz).
    
    Features:
        - Tabellenzählung mit Fortsetzungs-Erkennung (spanning tables)
        - Präzise Seiten-Zuordnung pro Tabelle
        - CSV-Extraktion mit Daten
        - Bild-Deduplizierung
        - Paragraph-Zählung (ohne Header/Footer)
        - Mathe-Erkennung
    """
    
    def __init__(
        self,
        table_strategy: str = "lines_strict",
        detect_continuations: bool = True,
        deduplicate_images: bool = True,
        extract_data: bool = True  # NEU: Tabellen-Daten extrahieren
    ):
        super().__init__()
        self.table_strategy = table_strategy
        self.detect_continuations = detect_continuations
        self.deduplicate_images = deduplicate_images
        self.extract_data = extract_data
        
        # Name für Anzeige
        cont_str = "+cont" if detect_continuations else ""
        self._name = f"PyMuPDF ({table_strategy}{cont_str})"
        
        # Schwellenwerte
        self.HEADER_ZONE = 0.08
        self.FOOTER_ZONE = 0.92
        self.MIN_PARAGRAPH_LEN = 10
        self.CONTINUATION_BOTTOM = 0.80
        self.CONTINUATION_TOP = 0.20
    
    def is_available(self) -> bool:
        try:
            import fitz
            return True
        except ImportError:
            return False
    
    def supports_continuation_detection(self) -> bool:
        return self.detect_continuations
    
    def supports_csv_extraction(self) -> bool:
        return self.extract_data and PANDAS_AVAILABLE
    
    def extract(self, source: Union[Path, bytes], filename: str = "") -> ExtractionResult:
        """Extrahiert alle Metriken aus einem PDF."""
        result = ExtractionResult(
            tool_name=self.name,
            file_path=filename or str(source)
        )
        
        try:
            import fitz
            start = time.perf_counter()
            
            # Öffne PDF
            if isinstance(source, bytes):
                doc = fitz.open(stream=source, filetype="pdf")
            else:
                doc = fitz.open(source)
            
            result.pages = len(doc)
            
            # Extrahiere alles
            tables_result = self._extract_tables_detailed(doc)
            images = self._extract_images(doc)
            content = self._extract_content(doc)
            
            doc.close()
            
            result.table_count = tables_result["count"]
            result.tables = tables_result["tables"]
            result.tables_data = tables_result["legacy_data"]
            result.image_count = images["unique"]
            result.image_count_total = images["total"]
            result.paragraphs = content["paragraphs"]
            result.math_formulas = content["math"]
            result.execution_time_ms = (time.perf_counter() - start) * 1000
            
            result.metadata = {
                "strategy": self.table_strategy,
                "continuations_detected": tables_result.get("continuations", 0),
                "spanning_tables": tables_result.get("spanning_count", 0),
                "data_extracted": self.extract_data
            }
            
        except Exception as e:
            result.error = str(e)
        
        return result
    
    def _extract_tables_detailed(self, doc) -> dict:
        """
        Extrahiert Tabellen mit detaillierter Seiten-Zuordnung und Daten.
        """
        import fitz
        
        extracted_tables: List[ExtractedTable] = []
        legacy_data: List[dict] = []
        
        logical_table_id = 0
        total_continuations = 0
        
        # Tracking für Spanning-Tabellen
        last_table_info: Optional[dict] = None
        current_spanning_table: Optional[ExtractedTable] = None
        spanning_data: List[List[Any]] = []  # Sammelt Daten über Seiten
        
        for page_num, page in enumerate(doc):
            page_number = page_num + 1
            page_height = page.rect.height
            
            try:
                tables_result = page.find_tables(strategy=self.table_strategy)
                page_tables = tables_result.tables
            except Exception:
                page_tables = []
            
            for idx, table in enumerate(page_tables):
                is_first_on_page = (idx == 0)
                is_continuation = False
                
                # Prüfe ob erste Tabelle der Seite eine Fortsetzung ist
                if is_first_on_page and self.detect_continuations and last_table_info:
                    is_continuation = self._is_continuation(
                        table, last_table_info, page_height
                    )
                
                # Extrahiere Tabellen-Daten
                table_data = []
                if self.extract_data:
                    try:
                        # PyMuPDF table.extract() gibt Liste von Listen zurück
                        table_data = table.extract()
                        # Bereinige None-Werte
                        table_data = [
                            [cell if cell is not None else "" for cell in row]
                            for row in table_data
                        ]
                    except Exception:
                        table_data = []
                
                if is_continuation:
                    total_continuations += 1
                    
                    # Aktualisiere die spanning Tabelle
                    if current_spanning_table:
                        current_spanning_table.continues_to_page = page_number
                        # Füge Daten hinzu (ohne Header)
                        if table_data and len(table_data) > 0:
                            spanning_data.extend(table_data)
                            current_spanning_table.data = spanning_data.copy()
                            current_spanning_table.rows = len(spanning_data)
                    
                    # Füge Continuation-Marker hinzu
                    cont_table = ExtractedTable(
                        table_id=current_spanning_table.table_id if current_spanning_table else logical_table_id,
                        page=page_number,
                        rows=len(table_data),
                        cols=table.col_count,
                        bbox=table.bbox,
                        is_continuation=True,
                        data=table_data
                    )
                    extracted_tables.append(cont_table)
                    
                    legacy_data.append({
                        "page": page_number,
                        "rows": len(table_data),
                        "cols": table.col_count,
                        "is_continuation": True
                    })
                else:
                    # Neue logische Tabelle
                    logical_table_id += 1
                    spanning_data = table_data.copy() if table_data else []
                    
                    # Header-Erkennung (einfache Heuristik)
                    header_row = self._detect_header_row(table_data) if table_data else None
                    
                    new_table = ExtractedTable(
                        table_id=logical_table_id,
                        page=page_number,
                        rows=len(table_data),
                        cols=table.col_count,
                        bbox=table.bbox,
                        is_continuation=False,
                        continues_to_page=None,
                        data=table_data,
                        header_row=header_row
                    )
                    extracted_tables.append(new_table)
                    current_spanning_table = new_table
                    
                    legacy_data.append({
                        "page": page_number,
                        "rows": len(table_data),
                        "cols": table.col_count,
                        "is_continuation": False
                    })
                
                # Update Tracking
                last_table_info = {
                    "cols": table.col_count,
                    "y1": table.bbox[3],
                    "page_height": page_height,
                    "page": page_number
                }
            
            # Wenn keine Tabellen auf der Seite: Reset Tracking
            if not page_tables:
                last_table_info = None
                current_spanning_table = None
                spanning_data = []
        
        # Zähle nur Haupt-Tabellen
        main_tables = [t for t in extracted_tables if not t.is_continuation]
        spanning_count = sum(1 for t in main_tables if t.is_spanning)
        
        return {
            "count": len(main_tables),
            "tables": extracted_tables,
            "legacy_data": legacy_data,
            "continuations": total_continuations,
            "spanning_count": spanning_count
        }
    
    def _detect_header_row(self, data: List[List[Any]]) -> Optional[int]:
        """
        Einfache Heuristik zur Header-Erkennung.
        
        Prüft ob erste Zeile sich von Rest unterscheidet:
        - Enthält keine Zahlen
        - Kürzere Texte
        - Alles Strings
        """
        if not data or len(data) < 2:
            return None
        
        first_row = data[0]
        
        # Prüfe ob erste Zeile nur Text enthält (keine reinen Zahlen)
        all_text = all(
            isinstance(cell, str) and not self._is_numeric(cell)
            for cell in first_row if cell
        )
        
        if all_text:
            return 0
        
        return None
    
    def _is_numeric(self, value: str) -> bool:
        """Prüft ob ein String eine Zahl ist."""
        if not value:
            return False
        # Entferne Tausender-Trennzeichen und Währungssymbole
        cleaned = re.sub(r'[€$£¥,.\s]', '', str(value))
        return cleaned.isdigit() or cleaned.lstrip('-').isdigit()
    
    def _is_continuation(self, table, last_info: dict, page_height: float) -> bool:
        """Prüft ob Tabelle eine Fortsetzung der vorherigen ist."""
        same_cols = table.col_count == last_info["cols"]
        was_at_bottom = last_info["y1"] > last_info["page_height"] * self.CONTINUATION_BOTTOM
        starts_at_top = table.bbox[1] < page_height * self.CONTINUATION_TOP
        return same_cols and was_at_bottom and starts_at_top
    
    def _extract_images(self, doc) -> dict:
        """Extrahiert Bilder mit Deduplizierung."""
        seen_xrefs = set()
        total = 0
        unique = 0
        
        for page in doc:
            images = page.get_images()
            total += len(images)
            
            for img in images:
                xref = img[0]
                if xref not in seen_xrefs:
                    seen_xrefs.add(xref)
                    unique += 1
        
        return {
            "total": total,
            "unique": unique if self.deduplicate_images else total
        }
    
    def _extract_content(self, doc) -> dict:
        """Extrahiert Paragraphen und Mathe-Indikatoren."""
        paragraphs = 0
        math_pages = 0
        
        math_fonts = ("math", "cmsy", "cmmi", "symbol")
        math_symbols = frozenset(["∑", "∫", "√", "≠", "≈", "∞", "∂", "π"])
        
        for page in doc:
            page_height = page.rect.height
            header_thresh = page_height * self.HEADER_ZONE
            footer_thresh = page_height * self.FOOTER_ZONE
            
            blocks = page.get_text("blocks")
            for block in blocks:
                y0, y1 = block[1], block[3]
                block_type = block[6]
                
                if block_type != 0:
                    continue
                if y1 < header_thresh or y0 > footer_thresh:
                    continue
                
                text = block[4].strip()
                if len(text) > self.MIN_PARAGRAPH_LEN and not re.match(r'^\d+$', text):
                    paragraphs += 1
            
            fonts = page.get_fonts()
            has_math_font = any(
                any(mf in f[3].lower() for mf in math_fonts) 
                for f in fonts
            )
            
            if has_math_font:
                math_pages += 1
            else:
                text = page.get_text()
                if any(sym in text for sym in math_symbols):
                    math_pages += 1
        
        return {"paragraphs": paragraphs, "math": math_pages}
