"""
Tabula Extractor.
Java-basierte Tabellen-Extraktion mit nativem DataFrame-Support.
"""

import tempfile
import os
from pathlib import Path
from typing import Union, List, Any, Optional
import time

from .base import BaseExtractor, ExtractionResult, ExtractedTable

try:
    import tabula
    TABULA_AVAILABLE = True
except ImportError:
    TABULA_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class TabulaExtractor(BaseExtractor):
    """
    Extractor basierend auf tabula-py.
    
    Vorteile:
        - Direkte DataFrame-Ausgabe
        - Bewährte Technologie
        - Gute Qualität
    
    Nachteile:
        - Benötigt Java
        - Langsamer Start
        - Keine Continuation Detection
    
    Args:
        mode: 'lattice' oder 'stream'
    """
    
    def __init__(
        self, 
        mode: str = "lattice",
        extract_data: bool = True
    ):
        super().__init__()
        self.mode = mode
        self.extract_data = extract_data
        self._name = f"Tabula ({mode})"

    def is_available(self) -> bool:
        return TABULA_AVAILABLE
    
    def supports_continuation_detection(self) -> bool:
        return False
    
    def supports_csv_extraction(self) -> bool:
        return self.extract_data and PANDAS_AVAILABLE

    def extract(self, source: Union[Path, bytes], filename: str = "") -> ExtractionResult:
        """Extrahiert Tabellen Seite für Seite mit DataFrames."""
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
                total_pages = 100
            
            result.pages = total_pages
            
            lattice_param = (self.mode == "lattice")
            stream_param = (self.mode == "stream")
            
            extracted_tables: List[ExtractedTable] = []
            legacy_data: List[dict] = []
            table_id = 0
            
            # Seite für Seite für genaue Zuordnung
            for page_num in range(1, total_pages + 1):
                try:
                    dfs = tabula.read_pdf(
                        file_path,
                        pages=str(page_num),
                        lattice=lattice_param,
                        stream=stream_param,
                        silent=True,
                        pandas_options={'header': None}  # Header manuell behandeln
                    )
                    
                    for df in dfs:
                        if df.empty:
                            continue
                        
                        table_id += 1
                        
                        # Daten extrahieren
                        table_data = []
                        if self.extract_data:
                            table_data = df.values.tolist()
                        
                        rows = len(df)
                        cols = len(df.columns)
                        
                        # Header-Erkennung
                        header_row = self._detect_header_row(table_data) if table_data else None
                        
                        # Wenn Header erkannt, DataFrame anpassen
                        df_final = df
                        if header_row == 0 and len(df) > 0:
                            df_final = pd.DataFrame(
                                df.values[1:],
                                columns=df.values[0]
                            )
                        
                        ext_table = ExtractedTable(
                            table_id=table_id,
                            page=page_num,
                            rows=rows,
                            cols=cols,
                            bbox=(),
                            is_continuation=False,
                            continues_to_page=None,
                            data=table_data,
                            dataframe=df_final if self.extract_data else None,
                            header_row=header_row
                        )
                        extracted_tables.append(ext_table)
                        
                        legacy_data.append({
                            "page": page_num,
                            "rows": rows,
                            "cols": cols,
                            "is_continuation": False
                        })
                        
                except Exception:
                    continue
            
            result.table_count = len(extracted_tables)
            result.tables = extracted_tables
            result.tables_data = legacy_data
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            result.metadata = {
                "mode": self.mode,
                "data_extracted": self.extract_data
            }

        except Exception as e:
            result.error = str(e)
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            
        finally:
            if temp_file and os.path.exists(file_path):
                os.unlink(file_path)
        
        return result
    
    def _detect_header_row(self, data: List[List[Any]]) -> Optional[int]:
        """Header-Erkennung."""
        if not data or len(data) < 2:
            return None
        
        first_row = data[0]
        
        # Prüfe ob erste Zeile nur Text enthält
        all_text = all(
            isinstance(cell, str) and not str(cell).replace('.', '').replace(',', '').isdigit()
            for cell in first_row if cell and str(cell).strip()
        )
        
        if all_text:
            return 0
        
        return None
