from magika import Magika

class FileIdentifier:
    """
    MODUL 1: Identifikation auf Dateisystem-Ebene.
    Verantwortung: Welcher Dateityp liegt vor?
    Technologie: Google Magika (Byte-Analysis)
    """
    def __init__(self):
        self._magika = Magika()

    def identify(self, file_bytes: bytes) -> dict:
        """
        Führt die reine Magika-Identifikation durch.
        """
        result = self._magika.identify_bytes(file_bytes)
        
        # Mapping basierend auf der aktuellen Magika API (v0.5+)
        # result ist ein MagikaResult Objekt
        return {
            "label": result.output.ct_label,      # z.B. 'pdf'
            "mime": result.output.mime_type,     # z.B. 'application/pdf'
            "group": result.output.group,        # z.B. 'document'
            "score": getattr(result, "score", 0.0) # Der Konfidenzwert
        }