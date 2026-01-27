"""
Tabula Extractor.
Java-basierte Tabellen-Extraktion.
"""

import tempfile
import os
from pathlib import Path
from typing import Union, List
import time

from .base import BaseExtractor, ExtractionResult, ExtractedTable

try:
    import tabula
    TABULA_AVAILABLE = True
except ImportError:
    TABULA_AVAILABLE = False


class TabulaExtractor(BaseExtractor):
    """
    Extractor basierend auf tabula-py.
    
    Hinweis: Tabula liefert standardmäßig keine Seiten-Information pro Tabelle.
    Wir müssen pages einzeln durchgehen für genaue Zuordnung.
    
    Args:
        mode: 'lattice' oder 'stream'
    """
    
    def __init__(self, mode: str = "lattice"):
        super().__init__()
        self.mode = mode
        self._name = f"Tabula ({mode})"

    def is_available(self) -> bool:
        return TABULA_AVAILABLE
    
    def supports_continuation_detection(self) -> bool:
        return False

    def extract(self, source: Union[Path, bytes], filename: str = "") -> ExtractionResult:
        """Extrahiert Tabellen Seite für Seite für genaue Zuordnung."""
        result = ExtractionResult(
            tool_name=self.name,
            file_path=filename or str(source)
        )
        
        start_time = time.perf_counter()

        temp_file = None
        file_path = str(source)

        if isinstance(source, bytes):
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file.write(source)
            temp_file.close()
            file_path = temp_file.name

        try:
            # Erst Seitenanzahl ermitteln
            try:
                import fitz
                doc = fitz.open(file_path)
                total_pages = len(doc)
                doc.close()
            except Exception:
                total_pages = 100  # Fallback: Versuche bis Seite 100
            
            result.pages = total_pages
            
            lattice_param = (self.mode == "lattice")
            stream_param = (self.mode == "stream")
            
            extracted_tables: List[ExtractedTable] = []
            legacy_data: List[dict] = []
            table_id = 0
            
            # Seite für Seite durchgehen für genaue Zuordnung
            for page_num in range(1, total_pages + 1):
                try:
                    dfs = tabula.read_pdf(
                        file_path,
                        pages=str(page_num),
                        lattice=lattice_param,
                        stream=stream_param,
                        silent=True
                    )
                    
                    for df in dfs:
                        if df.empty:
                            continue
                            
                        table_id += 1
                        rows = len(df)
                        cols = len(df.columns)
                        
                        ext_table = ExtractedTable(
                            table_id=table_id,
                            page=page_num,
                            rows=rows,
                            cols=cols,
                            bbox=(),  # Tabula liefert keine Bounding Box
                            is_continuation=False,
                            continues_to_page=None
                        )
                        extracted_tables.append(ext_table)
                        
                        legacy_data.append({
                            "page": page_num,
                            "rows": rows,
                            "cols": cols,
                            "is_continuation": False
                        })
                        
                except Exception:
                    # Seite hat keine Tabellen oder Fehler
                    continue
            
            result.table_count = len(extracted_tables)
            result.tables = extracted_tables
            result.tables_data = legacy_data
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000

        except Exception as e:
            result.error = str(e)
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            
        finally:
            if temp_file and os.path.exists(file_path):
                os.unlink(file_path)
        
        return result
