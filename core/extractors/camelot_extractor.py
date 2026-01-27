import tempfile
import os
from pathlib import Path
from typing import Union
from .base import BaseExtractor, ExtractionResult

# Versuch, Camelot zu importieren
try:
    import camelot
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False

class CamelotExtractor(BaseExtractor):
    def __init__(self, flavor="lattice"):
        """
        Args:
            flavor (str): 'lattice' (für Tabellen mit Linien) oder 'stream' (für Whitespace-Tabellen).
        """
        super().__init__()
        self.flavor = flavor
        # Der Name spiegelt die Konfiguration wider, damit man sie im Benchmark unterscheidet
        self._name = f"Camelot ({flavor})"

    def is_available(self) -> bool:
        return CAMELOT_AVAILABLE

    def extract(self, source: Union[Path, bytes], filename: str = "") -> ExtractionResult:
        import time
        start_time = time.time()
        
        # Camelot braucht einen Dateipfad. Wenn wir Bytes haben, temporäre Datei erstellen.
        temp_file = None
        file_path = str(source)
        
        if isinstance(source, bytes):
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file.write(source)
            temp_file.close()
            file_path = temp_file.name

        try:
            # Hier passiert die Magie: flavor='stream' oder 'lattice'
            tables = camelot.read_pdf(file_path, flavor=self.flavor, pages="all")
            
            table_count = len(tables)
            
            # Optional: Daten extrahieren, falls du sie später brauchst
            # data = [t.df for t in tables]

            return ExtractionResult(
                tool_name=self.name,
                file_path=filename,
                table_count=table_count,
                # Camelot macht keine Bilder/Seiten-Erkennung standardmäßig gut, daher 0 oder mocken
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            return ExtractionResult(
                tool_name=self.name,
                file_path=filename,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
        finally:
            # Aufräumen der Temp-Datei
            if temp_file and os.path.exists(file_path):
                os.unlink(file_path)