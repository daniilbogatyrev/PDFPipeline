import fitz  # PyMuPDF

class PDFInspector:
    """
    MODUL 2: Inhalts-Analyse für PDFs.
    Verantwortung: Ist die PDF nativ oder gescannt?
    Technologie: PyMuPDF (Strukturanalyse)
    """

    def inspect(self, file_bytes: bytes) -> dict:
        """
        Analysiert die interne Struktur der PDF.
        """
        report = {
            "sub_type": "UNKNOWN",
            "page_count": 0,
            "has_text": False,
            "text_length": 0,
            "image_count": 0
        }

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            report["page_count"] = len(doc)
            
            total_text = ""
            total_images = 0
            
            # Wir prüfen die ersten 5 Seiten für ein repräsentatives Ergebnis
            sample_pages = min(len(doc), 5)
            for i in range(sample_pages):
                page = doc[i]
                total_text += page.get_text().strip()
                total_images += len(page.get_images())

            report["text_length"] = len(total_text)
            report["has_text"] = len(total_text) > 50 # Heuristik-Grenze
            report["image_count"] = total_images

            # Entscheidungshierarchie
            if report["has_text"]:
                report["sub_type"] = "NATIVE"
            elif total_images >= sample_pages:
                report["sub_type"] = "SCANNED"
            else:
                report["sub_type"] = "EMPTY / VECTOR"

            doc.close()
        except Exception as e:
            report["sub_type"] = f"ERROR: {str(e)}"

        return report