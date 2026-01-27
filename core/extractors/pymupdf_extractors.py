"""
PyMuPDF Extractor.
Ersetzt den alten layout_analyzer.py mit verbesserter Logik.
"""

from pathlib import Path
from typing import Union, Optional
import time
import re

from .base import BaseExtractor, ExtractionResult


class PyMuPDFExtractor(BaseExtractor):
    """
    Extractor basierend auf PyMuPDF (fitz).
    
    Features:
        - Tabellenzählung mit Fortsetzungs-Erkennung
        - Bild-Deduplizierung
        - Paragraph-Zählung (ohne Header/Footer)
        - Mathe-Erkennung
    """
    
    def __init__(
        self,
        table_strategy: str = "lines_strict",
        detect_continuations: bool = True,
        deduplicate_images: bool = True
    ):
        super().__init__()
        self.table_strategy = table_strategy
        self.detect_continuations = detect_continuations
        self.deduplicate_images = deduplicate_images
        
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
            tables = self._extract_tables(doc)
            images = self._extract_images(doc)
            content = self._extract_content(doc)
            
            doc.close()
            
            result.table_count = tables["count"]
            result.tables_data = tables["data"]
            result.image_count = images["unique"]
            result.image_count_total = images["total"]
            result.paragraphs = content["paragraphs"]
            result.math_formulas = content["math"]
            result.execution_time_ms = (time.perf_counter() - start) * 1000
            
            result.metadata = {
                "strategy": self.table_strategy,
                "continuations_detected": tables.get("continuations", 0)
            }
            
        except Exception as e:
            result.error = str(e)
        
        return result
    
    def _extract_tables(self, doc) -> dict:
        """Extrahiert Tabellen mit Fortsetzungs-Erkennung."""
        tables_list = []
        table_count = 0
        continuations = 0
        last_table_info: Optional[dict] = None
        
        for page_num, page in enumerate(doc):
            page_height = page.rect.height
            
            try:
                tables_result = page.find_tables(strategy=self.table_strategy)
                page_tables = tables_result.tables
            except Exception:
                page_tables = []
            
            new_tables = len(page_tables)
            
            if page_tables:
                first_table = page_tables[0]
                
                # Prüfe Fortsetzung
                is_continuation = False
                if self.detect_continuations and last_table_info:
                    is_continuation = self._is_continuation(
                        first_table, last_table_info, page_height
                    )
                
                if is_continuation:
                    new_tables -= 1
                    continuations += 1
                
                # Speichere Details
                for idx, table in enumerate(page_tables):
                    tables_list.append({
                        "page": page_num + 1,
                        "rows": table.row_count,
                        "cols": table.col_count,
                        "is_continuation": (idx == 0 and is_continuation)
                    })
                
                # Update Tracking
                last_table = page_tables[-1]
                last_table_info = {
                    "cols": last_table.col_count,
                    "y1": last_table.bbox[3],
                    "page_height": page_height
                }
            else:
                last_table_info = None
            
            table_count += max(0, new_tables)
        
        return {"count": table_count, "data": tables_list, "continuations": continuations}
    
    def _is_continuation(self, table, last_info: dict, page_height: float) -> bool:
        """Prüft ob Tabelle eine Fortsetzung ist."""
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
            
            # Paragraphen (ohne Header/Footer)
            blocks = page.get_text("blocks")
            for block in blocks:
                y0, y1 = block[1], block[3]
                block_type = block[6]
                
                if block_type != 0:  # Nur Text-Blöcke
                    continue
                if y1 < header_thresh or y0 > footer_thresh:
                    continue
                
                text = block[4].strip()
                if len(text) > self.MIN_PARAGRAPH_LEN and not re.match(r'^\d+$', text):
                    paragraphs += 1
            
            # Mathe-Erkennung
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
