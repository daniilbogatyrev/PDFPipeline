from core.identifier import FileIdentifier
from core.inspector import PDFInspector
from core.layout_analyzer import LayoutAnalyzer

class DocumentOrchestrator:
    """
    Die zentrale Logik-Einheit. Sie steuert, welche Module 
    in welcher Reihenfolge auf ein Dokument angewendet werden.
    """
    def __init__(self):
        self.identifier = FileIdentifier()
        self.inspector = PDFInspector()
        # NEU: Analyzer initialisieren
        self.layout_analyzer = LayoutAnalyzer()

    def run_pipeline(self, file_bytes: bytes, filename: str) -> dict:
        """
        Führt die mehrstufige Analyse durch.
        """
        # --- Stufe 1: Identifikation ---
        id_results = self.identifier.identify(file_bytes)
        
        # Initialer Ergebnis-Container (State)
        pipeline_output = {
            "filename": filename,
            "format": id_results["label"],
            "mime": id_results["mime"],
            "confidence": id_results["score"],
            "pdf_details": None,       # Bleibt für Inspector-Ergebnisse (Native/Scan)
            "layout_stats": None,      # NEU: Für Tabellen/Bilder-Zählung
            "reasoning": None,         # NEU: Die Erklärung für den User
            "pipeline_status": "COMPLETED"
        }

        # --- Stufe 2: Bedingte Inspektion ---
        if id_results["label"] == "pdf":
            # 2a. Inspection (Native vs Scan)
            inspection_results = self.inspector.inspect(file_bytes)
            pipeline_output["pdf_details"] = inspection_results
            
            # 2b. Layout Analysis (Profile Report) - NEU
            # Wir nutzen das Ergebnis aus der Inspection ('sub_type'), um den Analyzer zu steuern
            sub_type = inspection_results["sub_type"]
            layout_results = self.layout_analyzer.analyze(file_bytes, sub_type)
            pipeline_output["layout_stats"] = layout_results

            # 2c. Reasoning generieren (Begründung für den User)
            pipeline_output["reasoning"] = self._generate_reasoning(sub_type, layout_results)

        else:
            pipeline_output["pipeline_status"] = "PARTIAL_NON_PDF"
            pipeline_output["reasoning"] = f"Format '{id_results['label']}' wird aktuell nur identifiziert."

        return pipeline_output

    def _generate_reasoning(self, sub_type: str, stats: dict) -> str:
        """Erzeugt die wissenschaftliche Begründung für die Pipeline-Wahl."""
        if sub_type == "NATIVE":
            return (f"Digitales PDF erkannt ({stats['paragraphs']} Textblöcke). "
                    f"Nutze deterministische Extraktion für {stats['tables']} Tabellen.")
        elif sub_type == "SCANNED":
            return ("Gescanntes Dokument (Pixel-basiert). "
                    "Aktiviere Vision-Pipeline & OCR für Informationsextraktion.")
        else:
            return "Unbekannter PDF-Typ oder Vektor-Grafik. Nutze Standard-Parsing."