"""
pdfplumber Extractor.
Alternative zu PyMuPDF für Benchmark-Vergleiche.
"""

from pathlib import Path
from typing import Union
import time
import io

from .base import BaseExtractor, ExtractionResult


class PDFPlumberExtractor(BaseExtractor):
    """
    Extractor basierend auf pdfplumber.
    Gut für Tabellen ohne sichtbare Linien.
    """
    
    def __init__(self, deduplicate_images: bool = True):
        super().__init__()
        self._name = "pdfplumber"
        self.deduplicate_images = deduplicate_images
    
    def is_available(self) -> bool:
        try:
            import pdfplumber
            return True
        except ImportError:
            return False
    
    def extract(self, source: Union[Path, bytes], filename: str = "") -> ExtractionResult:
        """Extrahiert Tabellen und Bilder."""
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
            
            tables_list = []
            table_count = 0
            total_images = 0
            seen_hashes = set()
            unique_images = 0
            
            for page_num, page in enumerate(pdf.pages):
                # Tabellen
                tables = page.find_tables()
                for idx, table in enumerate(tables):
                    table_count += 1
                    extracted = table.extract()
                    tables_list.append({
                        "page": page_num + 1,
                        "rows": len(extracted) if extracted else 0,
                        "cols": len(extracted[0]) if extracted and extracted[0] else 0,
                    })
                
                # Bilder
                images = page.images
                total_images += len(images)
                
                for img in images:
                    img_hash = (img.get('width'), img.get('height'), img.get('name', ''))
                    if img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        unique_images += 1
            
            pdf.close()
            
            result.table_count = table_count
            result.tables_data = tables_list
            result.image_count = unique_images if self.deduplicate_images else total_images
            result.image_count_total = total_images
            result.execution_time_ms = (time.perf_counter() - start) * 1000
            
        except ImportError:
            result.error = "pdfplumber nicht installiert"
        except Exception as e:
            result.error = str(e)
        
        return result
