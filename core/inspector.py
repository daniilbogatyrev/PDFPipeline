"""
MODUL 2: Inhalts-Analyse für PDFs.
Unterscheidet zwischen Native, Scanned, OCR-ed und Vector.
"""

import fitz  # PyMuPDF


class PDFInspector:
    """
    Analysiert PDF-Inhalte und klassifiziert den Dokumenttyp.
    
    Typen:
        - NATIVE: Digitales PDF mit extrahierbarem Text
        - SCANNED: Gescanntes Dokument (Bild-basiert)
        - VECTOR_GRAPHIC: Vektor-Grafiken (CAD, Charts)
        - EMPTY: Leeres Dokument
    """
    
    # Konfigurierbare Schwellenwerte
    MIN_TEXT_LENGTH = 50
    MIN_VECTOR_COUNT = 10
    SAMPLE_PAGE_COUNT = 5

    def inspect(self, file_bytes: bytes) -> dict:
        """
        Inspiziert ein PDF und klassifiziert seinen Typ.
        
        Returns:
            dict mit sub_type, pages, text_coverage_pct, etc.
        """
        report = {
            "sub_type": "UNKNOWN",
            "pages": 0,
            "text_coverage_pct": 0.0,
            "image_count": 0,
            "vector_paths": 0,
            "is_encrypted": False
        }

        doc = None
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            
            if doc.is_encrypted:
                report["is_encrypted"] = True
            
            report["pages"] = len(doc)
            
            # Sampling: Prüfe bis zu N Seiten
            sample_pages = min(len(doc), self.SAMPLE_PAGE_COUNT)
            
            text_pages = 0
            image_pages = 0
            vector_pages = 0
            total_text_len = 0
            
            for i in range(sample_pages):
                page = doc[i]
                
                # 1. Text-Analyse
                text = page.get_text()
                total_text_len += len(text)
                has_text = len(text.strip()) > self.MIN_TEXT_LENGTH
                
                # 2. Bild-Analyse
                images = page.get_images()
                report["image_count"] += len(images)
                has_images = len(images) > 0
                
                # 3. Vektor-Analyse
                drawings = page.get_drawings()
                report["vector_paths"] += len(drawings)
                has_vectors = len(drawings) > self.MIN_VECTOR_COUNT
                
                # Klassifizierung der Seite
                if has_text:
                    text_pages += 1
                elif has_images:
                    image_pages += 1
                elif has_vectors:
                    vector_pages += 1
            
            # Finale Entscheidung (Voting)
            if text_pages >= (sample_pages / 2):
                report["sub_type"] = "NATIVE"
            elif image_pages > vector_pages:
                report["sub_type"] = "SCANNED"
            elif vector_pages > 0:
                report["sub_type"] = "VECTOR_GRAPHIC"
            else:
                report["sub_type"] = "EMPTY"

            # Text-Dichte Metrik
            if report["pages"] > 0:
                report["text_coverage_pct"] = round(total_text_len / report["pages"], 1)

        except Exception as e:
            report["sub_type"] = "ERROR"
            report["error_msg"] = str(e)
        
        finally:
            if doc is not None:
                doc.close()

        return report
