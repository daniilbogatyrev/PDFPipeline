"""
Camelot Extractor.
Spezialisiert auf Tabellen mit Linien (lattice) oder Whitespace (stream).
"""

import tempfile
import os
from pathlib import Path
from typing import Union, List
import time

from .base import BaseExtractor, ExtractionResult, ExtractedTable

# Versuch, Camelot zu importieren
try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False


class CamelotExtractor(BaseExtractor):
    """
    Extractor basierend auf Camelot.
    
    Args:
        flavor: 'lattice' (für Tabellen mit Linien) oder 'stream' (für Whitespace-Tabellen)
    """
    
    def __init__(self, flavor: str = "lattice"):
        super().__init__()
        self.flavor = flavor
        self._name = f"Camelot ({flavor})"

    def is_available(self) -> bool:
        return CAMELOT_AVAILABLE
    
    def supports_continuation_detection(self) -> bool:
        return False  # Camelot erkennt keine spanning tables

    def extract(self, source: Union[Path, bytes], filename: str = "") -> ExtractionResult:
        """Extrahiert Tabellen mit Seiten-Details."""
        result = ExtractionResult(
            tool_name=self.name,
            file_path=filename or str(source)
        )
        
        start_time = time.perf_counter()
        
        # Camelot braucht einen Dateipfad
        temp_file = None
        file_path = str(source)
        
        if isinstance(source, bytes):
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file.write(source)
            temp_file.close()
            file_path = temp_file.name

        try:
            # Camelot extrahiert Tabellen
            tables = camelot.read_pdf(file_path, flavor=self.flavor, pages="all")
            
            extracted_tables: List[ExtractedTable] = []
            legacy_data: List[dict] = []
            
            for idx, table in enumerate(tables):
                table_id = idx + 1
                
                # Camelot liefert die Seite direkt
                page_number = table.page
                
                # DataFrame für Dimensionen
                df = table.df
                rows = len(df)
                cols = len(df.columns)
                
                # Bounding Box (Camelot speichert das in _bbox)
                bbox = tuple(table._bbox) if hasattr(table, '_bbox') else ()
                
                ext_table = ExtractedTable(
                    table_id=table_id,
                    page=page_number,
                    rows=rows,
                    cols=cols,
                    bbox=bbox,
                    is_continuation=False,
                    continues_to_page=None
                )
                extracted_tables.append(ext_table)
                
                legacy_data.append({
                    "page": page_number,
                    "rows": rows,
                    "cols": cols,
                    "is_continuation": False
                })
            
            result.table_count = len(extracted_tables)
            result.tables = extracted_tables
            result.tables_data = legacy_data
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Camelot macht keine Bilder/Seiten-Erkennung
            # Wir könnten PyMuPDF nutzen um pages zu bekommen
            try:
                import fitz
                doc = fitz.open(file_path)
                result.pages = len(doc)
                doc.close()
            except Exception:
                pass
            
        except Exception as e:
            result.error = str(e)
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            
        finally:
            # Aufräumen der Temp-Datei
            if temp_file and os.path.exists(file_path):
                os.unlink(file_path)
        
        return result
