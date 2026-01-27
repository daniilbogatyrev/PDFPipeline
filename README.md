# 🔬 DocIntel Lab - PDF Pipeline & Benchmarking

## Projektbeschreibung
Dieses Projekt ist eine modulare Pipeline zur intelligenten Analyse von PDF-Dokumenten. Es hilft dabei, Dokumente automatisch zu klassifizieren und wichtige Strukturen wie Tabellen und Bilder präzise zu extrahieren.

## Kern-Features
* **Intelligente Identifikation**: Nutzt Google Magika für eine zuverlässige Dateityperkennung auf Byte-Ebene.
* **Inhalts-Inspektion**: Der `PDFInspector` unterscheidet zwischen digitalen (NATIVE) und gescannten (SCANNED) Dokumenten, indem er Textdichte und Vektorgrafiken analysiert.
* **Präzise Extraktion**: 
    * **Tabellen**: Erkennt zusammenhängende Tabellen über Seitengrenzen hinweg (Continuation Detection).
    * **Bilder**: Automatische Deduplizierung, damit das gleiche Logo nicht mehrfach gezählt wird.
* **Benchmarking**: Vergleicht verschiedene Tools (PyMuPDF vs. pdfplumber) direkt gegen eine definierte "Ground Truth" (Soll-Werte).

## Projektstruktur
* `app.py`: Das User-Interface (Streamlit) für den Browser.
* `core/`: Die Logik-Zentrale.
    * `orchestrator.py`: Steuert den gesamten Ablauf (Identifizieren -> Inspizieren -> Extrahieren).
    * `extractors/`: Enthält die verschiedenen Analyse-Werkzeuge.
* `benchmark/`: Werkzeuge zum Messen der Genauigkeit und Geschwindigkeit.

## Installation & Start
1. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt