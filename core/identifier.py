"""
MODUL 1: Identifikation auf Dateisystem-Ebene.
Verantwortung: Welcher Dateityp liegt vor?
Technologie: Google Magika (Byte-Analysis)
"""

from magika import Magika


class FileIdentifier:
    """
    Identifiziert Dateitypen mittels Google Magika.
    """
    
    def __init__(self):
        self._magika = Magika()

    def identify(self, file_bytes: bytes) -> dict:
        """
        Führt die Magika-Identifikation durch.
        
        Returns:
            dict mit label, mime, group, score
        """
        result = self._magika.identify_bytes(file_bytes)
        
        return {
            "label": result.output.ct_label,      # z.B. 'pdf'
            "mime": result.output.mime_type,      # z.B. 'application/pdf'
            "group": result.output.group,         # z.B. 'document'
            "score": getattr(result.output, "score", 0.0)
        }
