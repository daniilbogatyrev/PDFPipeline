"""
Camelot Extractor.
Spezialisiert auf hochwertige Tabellen-Extraktion mit CSV-Support.
"""

import tempfile
import os
from pathlib import Path
from typing import Union, List, Any, Optional
import time

from .base import BaseExtractor, ExtractionResult, ExtractedTable

# Versuch, Camelot zu importieren
try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False

# Optional pandas
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class CamelotExtractor(BaseExtractor):
    """
    Extractor basierend auf Camelot.
    
    Vorteile:
        - Sehr hohe CSV-Qualität
        - Gute Merged-Cell Behandlung
        - Accuracy Score pro Tabelle
    
    Nachteile:
        - Benötigt Ghostscript
        - Langsamer
        - Keine Continuation Detection
    
    Args:
        flavor: 'lattice' (für Tabellen mit Linien) oder 'stream' (für Whitespace-Tabellen)
    """
    
    def __init__(
        self, 
        flavor: str = "lattice",
        extract_data: bool = True
    ):
        super().__init__()
        self.flavor = flavor
        self.extract_data = extract_data
        self._name = f"Camelot ({flavor})"

    def is_available(self) -> bool:
        return CAMELOT_AVAILABLE
    
    def supports_continuation_detection(self) -> bool:
        return False
    
    def supports_csv_extraction(self) -> bool:
        return self.extract_data and PANDAS_AVAILABLE

    def extract(self, source: Union[Path, bytes], filename: str = "") -> ExtractionResult:
        """Extrahiert Tabellen mit Daten und Qualitäts-Scores."""
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
            tables = camelot.read_pdf(
                file_path, 
                flavor=self.flavor, 
                pages="all",
                suppress_stdout=True
            )
            
            extracted_tables: List[ExtractedTable] = []
            legacy_data: List[dict] = []
            total_accuracy = 0.0
            
            for idx, table in enumerate(tables):
                table_id = idx + 1
                page_number = table.page
                
                # DataFrame und Daten
                df = table.df
                table_data = []
                
                if self.extract_data:
                    # Konvertiere DataFrame zu Liste von Listen
                    table_data = df.values.tolist()
                    # Füge Header hinzu wenn vorhanden
                    if list(df.columns) != list(range(len(df.columns))):
                        table_data.insert(0, list(df.columns))
                
                rows = len(df)
                cols = len(df.columns)
                
                # Bounding Box
                bbox = tuple(table._bbox) if hasattr(table, '_bbox') else ()
                
                # Accuracy Score (Camelot-spezifisch)
                accuracy = table.accuracy if hasattr(table, 'accuracy') else 0.0
                total_accuracy += accuracy
                
                # Header-Erkennung
                header_row = 0 if table_data else None  # Camelot setzt Header meist richtig
                
                ext_table = ExtractedTable(
                    table_id=table_id,
                    page=page_number,
                    rows=rows,
                    cols=cols,
                    bbox=bbox,
                    is_continuation=False,
                    continues_to_page=None,
                    data=table_data,
                    dataframe=df if self.extract_data else None,
                    header_row=header_row
                )
                extracted_tables.append(ext_table)
                
                legacy_data.append({
                    "page": page_number,
                    "rows": rows,
                    "cols": cols,
                    "accuracy": accuracy,
                    "is_continuation": False
                })
            
            result.table_count = len(extracted_tables)
            result.tables = extracted_tables
            result.tables_data = legacy_data
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            
            # Seitenanzahl ermitteln
            try:
                import fitz
                doc = fitz.open(file_path)
                result.pages = len(doc)
                doc.close()
            except Exception:
                pass
            
            # Metadata
            avg_accuracy = total_accuracy / len(tables) if tables else 0.0
            result.metadata = {
                "flavor": self.flavor,
                "avg_accuracy": round(avg_accuracy, 2),
                "data_extracted": self.extract_data
            }
            
        except Exception as e:
            result.error = str(e)
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            
        finally:
            if temp_file and os.path.exists(file_path):
                os.unlink(file_path)
        
        return result
