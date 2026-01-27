"""
Document Orchestrator.
Zentrale Pipeline-Steuerung für Dokumentanalyse.
"""

from .identifier import FileIdentifier
from .inspector import PDFInspector
from .extractors import get_default_extractor


class DocumentOrchestrator:
    """
    Zentrale Pipeline-Steuerung.
    
    Pipeline:
        1. Identifier (Magika): Dateityp erkennen
        2. Inspector: Native vs Scanned unterscheiden
        3. Extractor: Tabellen, Bilder, etc. zählen
    """
    
    def __init__(self):
        self.identifier = FileIdentifier()
        self.inspector = PDFInspector()
        self.extractor = get_default_extractor()

    def run_pipeline(self, file_bytes: bytes, filename: str) -> dict:
        """
        Führt die mehrstufige Analyse durch.
        
        Returns:
            dict mit allen Analyse-Ergebnissen
        """
        # Stufe 1: Identifikation (Magika)
        id_results = self.identifier.identify(file_bytes)
        
        pipeline_output = {
            "filename": filename,
            "format": id_results["label"],
            "mime": id_results["mime"],
            "confidence": id_results["score"],
            "pdf_details": None,
            "layout_stats": None,
            "reasoning": None,
            "pipeline_status": "COMPLETED"
        }

        # Stufe 2 & 3: Nur für PDFs
        if id_results["label"] == "pdf":
            # 2a. Inspection (Native vs Scanned)
            inspection_results = self.inspector.inspect(file_bytes)
            pipeline_output["pdf_details"] = inspection_results
            
            sub_type = inspection_results["sub_type"]
            
            # 2b. Extraktion (nur für Native PDFs sinnvoll)
            if sub_type == "NATIVE":
                extraction = self.extractor.extract(file_bytes, filename)
                
                pipeline_output["layout_stats"] = {
                    "tables": extraction.table_count,
                    "tables_detail": extraction.get_table_summary(),
                    "tables_by_page": extraction.tables_by_page,
                    "images": extraction.image_count,
                    "images_total": extraction.image_count_total,
                    "paragraphs": extraction.paragraphs,
                    "math_formulas": extraction.math_formulas,
                    "pages": extraction.pages
                }
            else:
                # Für Scanned/Vector: Keine Extraktion möglich
                pipeline_output["layout_stats"] = {
                    "tables": 0,
                    "tables_detail": "N/A (OCR benötigt)",
                    "images": inspection_results.get("image_count", 0),
                    "images_total": inspection_results.get("image_count", 0),
                    "paragraphs": 0,
                    "math_formulas": 0,
                    "pages": inspection_results.get("pages", 0),
                    "requires_ocr": sub_type == "SCANNED"
                }
            
            # Reasoning
            pipeline_output["reasoning"] = self._generate_reasoning(
                sub_type, pipeline_output["layout_stats"]
            )
        else:
            pipeline_output["pipeline_status"] = "PARTIAL_NON_PDF"
            pipeline_output["reasoning"] = f"Format '{id_results['label']}' wird aktuell nur identifiziert."

        return pipeline_output

    def _generate_reasoning(self, sub_type: str, stats: dict) -> str:
        """Erzeugt die Begründung für den User."""
        if sub_type == "NATIVE":
            return (
                f"Digitales PDF erkannt ({stats.get('paragraphs', 0)} Textblöcke). "
                f"Nutze deterministische Extraktion für {stats.get('tables', 0)} Tabellen."
            )
        elif sub_type == "SCANNED":
            return (
                "Gescanntes Dokument (Pixel-basiert). "
                "Für Tabellen-/Texterkennung ist OCR erforderlich."
            )
        elif sub_type == "VECTOR_GRAPHIC":
            return "Vektor-Grafik erkannt. Nutze spezialisierte Vektor-Extraktion."
        else:
            return "Unbekannter PDF-Typ. Standard-Parsing aktiv."
