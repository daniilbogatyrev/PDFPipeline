"""
pdfplumber Extractor.
Alternative zu PyMuPDF mit guter CSV-Extraktion.
"""

from pathlib import Path
from typing import Union, List, Any, Optional
import time
import io
import re

from .base import BaseExtractor, ExtractionResult, ExtractedTable

# Optional pandas
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class PDFPlumberExtractor(BaseExtractor):
    """
    Extractor basierend auf pdfplumber.
    
    Vorteile:
        - Sehr gute Tabellen-Extraktion, auch ohne sichtbare Linien
        - Zuverlässige CSV-Daten
        - Gute Header-Erkennung
    
    Nachteile:
        - Keine Continuation Detection
        - Langsamer als PyMuPDF
    """
    
    def __init__(
        self, 
        deduplicate_images: bool = True,
        extract_data: bool = True,
        table_settings: Optional[dict] = None
    ):
        super().__init__()
        self._name = "pdfplumber"
        self.deduplicate_images = deduplicate_images
        self.extract_data = extract_data
        
        # Tabellen-Einstellungen für pdfplumber
        self.table_settings = table_settings or {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
            "join_tolerance": 3,
        }
    
    def is_available(self) -> bool:
        try:
            import pdfplumber
            return True
        except ImportError:
            return False
    
    def supports_continuation_detection(self) -> bool:
        return False
    
    def supports_csv_extraction(self) -> bool:
        return self.extract_data and PANDAS_AVAILABLE
    
    def extract(self, source: Union[Path, bytes], filename: str = "") -> ExtractionResult:
        """Extrahiert Tabellen und Bilder mit Daten."""
        result = ExtractionResult(
            tool_name=self.name,
            file_path=filename or str(source)
        )
        
        try:
            import pdfplumber
            start = time.perf_counter()
            
            # Öffne PDF
            if isinstance(source, bytes):
                pdf = pdfplumber.open(io.BytesIO(source))
            else:
                pdf = pdfplumber.open(source)
            
            result.pages = len(pdf.pages)
            
            extracted_tables: List[ExtractedTable] = []
            legacy_data: List[dict] = []
            table_id = 0
            
            total_images = 0
            seen_hashes = set()
            unique_images = 0
            
            for page_num, page in enumerate(pdf.pages):
                page_number = page_num + 1
                
                # Tabellen extrahieren
                tables = page.find_tables(table_settings=self.table_settings)
                
                for table in tables:
                    table_id += 1
                    
                    # Daten extrahieren
                    table_data = []
                    if self.extract_data:
                        try:
                            extracted = table.extract()
                            if extracted:
                                # Bereinige None-Werte
                                table_data = [
                                    [cell if cell is not None else "" for cell in row]
                                    for row in extracted
                                ]
                        except Exception:
                            table_data = []
                    
                    # Header-Erkennung
                    header_row = self._detect_header_row(table_data) if table_data else None
                    
                    # Bounding Box
                    bbox = table.bbox if hasattr(table, 'bbox') else ()
                    
                    rows = len(table_data) if table_data else 0
                    cols = len(table_data[0]) if table_data and table_data[0] else 0
                    
                    ext_table = ExtractedTable(
                        table_id=table_id,
                        page=page_number,
                        rows=rows,
                        cols=cols,
                        bbox=bbox,
                        is_continuation=False,
                        continues_to_page=None,
                        data=table_data,
                        header_row=header_row
                    )
                    extracted_tables.append(ext_table)
                    
                    legacy_data.append({
                        "page": page_number,
                        "rows": rows,
                        "cols": cols,
                        "is_continuation": False
                    })
                
                # Bilder
                images = page.images
                total_images += len(images)
                
                for img in images:
                    img_hash = (
                        img.get('width'), 
                        img.get('height'), 
                        img.get('name', ''),
                        img.get('stream', b'')[:100] if img.get('stream') else ''
                    )
                    if img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        unique_images += 1
            
            pdf.close()
            
            result.table_count = len(extracted_tables)
            result.tables = extracted_tables
            result.tables_data = legacy_data
            result.image_count = unique_images if self.deduplicate_images else total_images
            result.image_count_total = total_images
            result.execution_time_ms = (time.perf_counter() - start) * 1000
            
            result.metadata = {
                "table_settings": self.table_settings,
                "data_extracted": self.extract_data
            }
            
        except ImportError:
            result.error = "pdfplumber nicht installiert"
        except Exception as e:
            result.error = str(e)
        
        return result
    
    def _detect_header_row(self, data: List[List[Any]]) -> Optional[int]:
        """Header-Erkennung."""
        if not data or len(data) < 2:
            return None
        
        first_row = data[0]
        
        # Prüfe ob erste Zeile nur Text enthält
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
        cleaned = re.sub(r'[€$£¥,.\s]', '', str(value))
        return cleaned.isdigit() or cleaned.lstrip('-').isdigit()


class PDFPlumberStreamExtractor(PDFPlumberExtractor):
    """
    pdfplumber mit Stream-Strategie für Tabellen ohne Linien.
    """
    
    def __init__(self, deduplicate_images: bool = True, extract_data: bool = True):
        super().__init__(
            deduplicate_images=deduplicate_images,
            extract_data=extract_data,
            table_settings={
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "snap_tolerance": 5,
                "join_tolerance": 5,
            }
        )
        self._name = "pdfplumber (stream)"
