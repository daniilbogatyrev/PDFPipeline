import fitz
import re

class LayoutAnalyzer:
    """
    MODUL 3: Strukturelle Profilierung.
    Verbessert durch: Geometrische Filterung (Header/Footer) & Deduplizierung.
    """
    
    def analyze(self, file_bytes: bytes, sub_type: str) -> dict:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        
        if sub_type == "NATIVE":
            results = self._analyze_native(doc)
        else:
            results = self._analyze_scanned(doc)
            
        doc.close()
        return results

    def _analyze_native(self, doc) -> dict:
        stats = {
            "tables": 0,
            "pages": len(doc), 
            "images": 0,             # Zählt jetzt Unique Images
            "images_total": 0,       # Zählt alle Bild-Vorkommen
            "paragraphs": 0, 
            "math_formulas": 0
        }
        
        last_table_info = None 
        seen_image_xrefs = set() # Für Deduplizierung (Logos etc.)

        for page in doc:
            page_height = page.rect.height
            
            # --- 1. Tabellen (Bestehende Logik mit Sicherheitsnetz) ---
            tables = page.find_tables(strategy="lines_strict")
            current_tables = tables.tables
            count_on_page = len(current_tables)
            
            if count_on_page > 0:
                first_table = current_tables[0]
                if last_table_info:
                    # Logik zur Erkennung von Tabellenfortsetzungen
                    prev_cols = last_table_info['cols']
                    curr_cols = first_table.col_count
                    prev_y1 = last_table_info['bbox'][3]
                    prev_page_h = last_table_info['page_height']
                    curr_y0 = first_table.bbox[1]
                    
                    # Sind Spalten identisch UND Abstand passt zum Seitenwechsel?
                    is_same_structure = (prev_cols == curr_cols)
                    # "Abreißkante": War die alte Tabelle ganz unten und die neue ganz oben?
                    is_continuation = (prev_y1 > prev_page_h * 0.85) and (curr_y0 < page_height * 0.25)
                    
                    if is_same_structure and is_continuation:
                        count_on_page -= 1 # Fortsetzung nicht neu zählen
                
                last_tbl = current_tables[-1]
                last_table_info = {
                    'cols': last_tbl.col_count,
                    'bbox': last_tbl.bbox,
                    'page_height': page_height
                }
            else:
                last_table_info = None

            stats["tables"] += max(0, count_on_page)

            # --- 2. Bilder (Dedupliziert) ---
            # get_images liefert: (xref, smask, width, height, bpc, colorspace, ...)
            image_list = page.get_images()
            stats["images_total"] += len(image_list)
            
            for img in image_list:
                xref = img[0] # Die interne ID des Bild-Objekts
                if xref not in seen_image_xrefs:
                    seen_image_xrefs.add(xref)
                    stats["images"] += 1

            # --- 3. Paragraphen (Mit Header/Footer Filter) ---
            blocks = page.get_text("blocks")
            # Definition der "Content Zone": Wir ignorieren Top 8% und Bottom 8%
            header_thresh = page_height * 0.08
            footer_thresh = page_height * 0.92
            
            for b in blocks:
                # b Struktur: (x0, y0, x1, y1, "text", block_no, block_type)
                x0, y0, x1, y1 = b[0], b[1], b[2], b[3]
                block_type = b[6]
                
                # Filter A: Block-Typ muss Text sein (0)
                if block_type != 0:
                    continue

                # Filter B: Geometrische Position (Header/Footer Removal)
                # Wenn der Block komplett im Header (y1 < thresh) oder Footer (y0 > thresh) liegt
                if y1 < header_thresh or y0 > footer_thresh:
                    continue 

                text_content = b[4].strip()
                
                # Filter C: Inhaltliche Qualität
                # Ignoriere reine Zahlen (oft Tabellenzellen, die als Block erkannt wurden) oder sehr kurze Schnipsel
                if len(text_content) > 10 and not re.match(r'^\d+$', text_content):
                    stats["paragraphs"] += 1

            # --- 4. Mathe (Granularer) ---
            # Wir prüfen, ob im "Content Bereich" Mathe-Fonts genutzt werden
            font_list = page.get_fonts()
            # math_fonts ist True, wenn auf der Seite Mathe-Fonts geladen werden
            math_fonts_present = any("math" in f[3].lower() or "cmsy" in f[3].lower() or "cmmi" in f[3].lower() for f in font_list)
            
            if math_fonts_present:
                # Wir erhöhen den Zähler, aber nur als Indikator für "Mathe-lastige Seite"
                # (Eine präzise Zählung einzelner Formeln ist ohne LaTeX-Parser extrem schwer)
                stats["math_formulas"] += 1
            else:
                # Fallback: Symbolsuche im Content-Text
                text_content = page.get_text()
                if any(sym in text_content for sym in ["∑", "∫", "√", "≠", "≈"]):
                    stats["math_formulas"] += 1

        return stats

    def _analyze_scanned(self, doc) -> dict:
        return {
            "tables": "Pending (Vision)",
            "images":  "Grobe Schätzung",
            "images_total": 0,
            "pages": len(doc),
            "paragraphs": 0, # Scan hat per Definition keine Text-Paragraphen ohne OCR
            "math_formulas": 0
        }