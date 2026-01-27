"""
pdfplumber Extractor.
Alternative zu PyMuPDF für Benchmark-Vergleiche.
Erweitert um detaillierte Tabellen-Informationen.
"""

from pathlib import Path
from typing import Union, List
import time
import io

from .base import BaseExtractor, ExtractionResult, ExtractedTable


class PDFPlumberExtractor(BaseExtractor):
    """
    Extractor basierend auf pdfplumber.
    Gut für Tabellen ohne sichtbare Linien.
    
    Hinweis: pdfplumber hat keine native Continuation-Detection.
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
    
    def supports_continuation_detection(self) -> bool:
        return False  # pdfplumber erkennt keine spanning tables
    
    def extract(self, source: Union[Path, bytes], filename: str = "") -> ExtractionResult:
        """Extrahiert Tabellen und Bilder mit Seiten-Details."""
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
                page_number = page_num + 1  # 1-basiert
                
                # Tabellen mit Bounding Box
                tables = page.find_tables()
                for table in tables:
                    table_id += 1
                    extracted = table.extract()
                    
                    # Bounding Box von pdfplumber
                    bbox = table.bbox if hasattr(table, 'bbox') else ()
                    
                    ext_table = ExtractedTable(
                        table_id=table_id,
                        page=page_number,
                        rows=len(extracted) if extracted else 0,
                        cols=len(extracted[0]) if extracted and extracted[0] else 0,
                        bbox=bbox,
                        is_continuation=False,  # pdfplumber erkennt das nicht
                        continues_to_page=None
                    )
                    extracted_tables.append(ext_table)
                    
                    # Legacy data
                    legacy_data.append({
                        "page": page_number,
                        "rows": ext_table.rows,
                        "cols": ext_table.cols,
                        "is_continuation": False
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
            
            result.table_count = len(extracted_tables)
            result.tables = extracted_tables
            result.tables_data = legacy_data
            result.image_count = unique_images if self.deduplicate_images else total_images
            result.image_count_total = total_images
            result.execution_time_ms = (time.perf_counter() - start) * 1000
            
        except ImportError:
            result.error = "pdfplumber nicht installiert"
        except Exception as e:
            result.error = str(e)
        
        return result
