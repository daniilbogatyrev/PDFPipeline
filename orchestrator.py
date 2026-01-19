from core.identifier import FileIdentifier
from core.inspector import PDFInspector

class DocumentOrchestrator:
    """
    Die zentrale Logik-Einheit. Sie steuert, welche Module 
    in welcher Reihenfolge auf ein Dokument angewendet werden.
    """
    def __init__(self):
        self.identifier = FileIdentifier()
        self.inspector = PDFInspector()

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
            "pdf_details": None,
            "pipeline_status": "COMPLETED"
        }

        # --- Stufe 2: Bedingte Inspektion ---
        if id_results["label"] == "pdf":
            # Hier triggert der Orchestrator den nächsten Schritt
            inspection_results = self.inspector.inspect(file_bytes)
            pipeline_output["pdf_details"] = inspection_results
        else:
            pipeline_output["pipeline_status"] = "PARTIAL_NON_PDF"

        return pipeline_output