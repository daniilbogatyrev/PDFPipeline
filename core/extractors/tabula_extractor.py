import tempfile
import os
from pathlib import Path
from typing import Union
from .base import BaseExtractor, ExtractionResult

try:
    import tabula
    TABULA_AVAILABLE = True
except ImportError:
    TABULA_AVAILABLE = False

class TabulaExtractor(BaseExtractor):
    def __init__(self, mode="lattice"):
        """
        Args:
            mode (str): 'lattice' oder 'stream'
        """
        super().__init__()
        self.mode = mode
        self._name = f"Tabula ({mode})"

    def is_available(self) -> bool:
        return TABULA_AVAILABLE

    def extract(self, source: Union[Path, bytes], filename: str = "") -> ExtractionResult:
        import time
        start_time = time.time()

        temp_file = None
        file_path = str(source)

        if isinstance(source, bytes):
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            temp_file.write(source)
            temp_file.close()
            file_path = temp_file.name

        try:
            lattice_param = True if self.mode == "lattice" else False
            stream_param = True if self.mode == "stream" else False

            # Tabula read_pdf gibt eine Liste von DataFrames zurück
            dfs = tabula.read_pdf(
                file_path, 
                pages="all", 
                lattice=lattice_param, 
                stream=stream_param,
                silent=True
            )
            
            return ExtractionResult(
                tool_name=self.name,
                file_path=filename,
                table_count=len(dfs),
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
            if temp_file and os.path.exists(file_path):
                os.unlink(file_path)