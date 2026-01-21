import fitz  # PyMuPDF

class PDFInspector:
    """
    MODUL 2: Inhalts-Analyse für PDFs.
    Unterscheidet präzise zwischen Native, Scanned, OCR-ed und Vector.
    """

    def inspect(self, file_bytes: bytes) -> dict:
        report = {
            "sub_type": "UNKNOWN",
            "pages": 0,
            "text_coverage_pct": 0.0,
            "image_count": 0,
            "vector_paths": 0,
            "is_encrypted": False
        }

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            
            if doc.is_encrypted:
                report["is_encrypted"] = True
                # Versuch, ohne Passwort zu lesen (oft möglich bei Owner-Passwörtern)
                # Wenn nicht möglich, bricht fitz oft eh vorher ab oder liefert leere Seiten
            
            report["pages"] = len(doc)
            
            # Sampling: Wir prüfen bis zu 5 Seiten (Anfang, Mitte, Ende wäre besser, 
            # aber die ersten 5 reichen meist für Homogenität)
            sample_pages = min(len(doc), 5)
            
            text_pages = 0
            image_pages = 0
            vector_pages = 0
            
            total_text_len = 0
            
            for i in range(sample_pages):
                page = doc[i]
                
                # 1. Text-Analyse
                text = page.get_text()
                total_text_len += len(text)
                
                # Wenn nennenswerter Text da ist (> 50 Zeichen pro Seite), zählt es als Text-Seite
                has_text = len(text.strip()) > 50
                
                # 2. Bild-Analyse (Pixel-Daten)
                images = page.get_images()
                report["image_count"] += len(images)
                
                # Eine Seite gilt als "Bild-Seite", wenn sie fast vollflächig von Bildern bedeckt ist
                # (Hier vereinfacht: Wenn mind. 1 Bild da ist und wenig Text)
                has_images = len(images) > 0
                
                # 3. Vektor-Analyse (Zeichnungen/Pfade)
                # get_drawings() holt Linien, Rechtecke, Kurven (wichtig für CAD/Charts)
                drawings = page.get_drawings()
                report["vector_paths"] += len(drawings)
                has_vectors = len(drawings) > 10 # Toleranz für einfache Linien
                
                # --- KLASSIFIZIERUNG DER SEITE ---
                if has_text:
                    text_pages += 1
                elif has_images:
                    image_pages += 1
                elif has_vectors:
                    vector_pages += 1
            
            doc.close()

            # --- FINALE ENTSCHEIDUNG (Voting) ---
            
            # Fall 1: Wir haben signifikanten Text.
            # Das deckt "Native PDF" UND "Searchable Scan" (OCR schon drin) ab.
            # Für die Pipeline ist das beides "NATIVE", weil wir Text extrahieren können.
            if text_pages >= (sample_pages / 2):
                report["sub_type"] = "NATIVE"
                
            # Fall 2: Keine Text, aber Bilder
            elif image_pages > vector_pages:
                report["sub_type"] = "SCANNED"
                
            # Fall 3: Weder Text noch Bilder, aber Vektoren
            elif vector_pages > 0:
                report["sub_type"] = "VECTOR_GRAPHIC"
                
            # Fall 4: Wirklich leer
            else:
                report["sub_type"] = "EMPTY"

            # Metrik für Data Science Zwecke
            if report["pages"] > 0:
                report["text_coverage_pct"] = round(total_text_len / report["pages"], 1)

        except Exception as e:
            report["sub_type"] = "ERROR"
            report["error_msg"] = str(e)

        return report