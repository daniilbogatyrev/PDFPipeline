"""
Table Exporter.
Exportiert einzelne Tabellen oder Tabellen-Bereiche als separate PDF-Dateien.
"""

import io
import zipfile
from pathlib import Path
from typing import Union, List, Optional, BinaryIO
from dataclasses import dataclass

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

from .extractors.base import ExtractedTable


@dataclass
class ExportedTable:
    """Ergebnis eines Tabellen-Exports."""
    table_id: int
    filename: str
    start_page: int
    end_page: int
    pdf_bytes: bytes
    page_count: int
    
    @property
    def size_kb(self) -> float:
        return len(self.pdf_bytes) / 1024


class TableExporter:
    """
    Exportiert Tabellen aus einem PDF als separate Dateien.
    
    Features:
        - Einzelne Tabelle exportieren
        - Mehrere Tabellen als ZIP exportieren
        - Seiten-Range basierter Export
        - Optional: Nur Tabellen-Bereich croppen (bbox)
    """
    
    def __init__(self, crop_to_table: bool = False):
        """
        Args:
            crop_to_table: Wenn True, wird die Seite auf den Tabellen-Bereich zugeschnitten
        """
        if not FITZ_AVAILABLE:
            raise ImportError("PyMuPDF (fitz) wird für den Export benötigt")
        
        self.crop_to_table = crop_to_table
    
    def export_table(
        self,
        source_pdf: Union[Path, bytes, BinaryIO],
        table: ExtractedTable,
        output_filename: Optional[str] = None
    ) -> ExportedTable:
        """
        Exportiert eine einzelne Tabelle als PDF.
        
        Args:
            source_pdf: Quell-PDF (Pfad, Bytes oder File-Handle)
            table: ExtractedTable mit Seiten-Informationen
            output_filename: Optionaler Dateiname (sonst generiert)
            
        Returns:
            ExportedTable mit den PDF-Bytes
        """
        # PDF öffnen
        doc = self._open_document(source_pdf)
        
        try:
            start_page, end_page = table.page_range
            
            # Neues PDF erstellen
            new_doc = fitz.open()
            
            # Seiten kopieren (0-basiert intern)
            for page_num in range(start_page - 1, end_page):
                if page_num < len(doc):
                    new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            # Optional: Croppen
            if self.crop_to_table and table.bbox and len(new_doc) == 1:
                self._crop_page_to_bbox(new_doc[0], table.bbox)
            
            # Als Bytes exportieren
            pdf_bytes = new_doc.tobytes()
            new_doc.close()
            
            # Dateiname generieren
            if not output_filename:
                if start_page == end_page:
                    output_filename = f"table_{table.table_id}_page_{start_page}.pdf"
                else:
                    output_filename = f"table_{table.table_id}_pages_{start_page}-{end_page}.pdf"
            
            return ExportedTable(
                table_id=table.table_id,
                filename=output_filename,
                start_page=start_page,
                end_page=end_page,
                pdf_bytes=pdf_bytes,
                page_count=end_page - start_page + 1
            )
            
        finally:
            doc.close()
    
    def export_tables(
        self,
        source_pdf: Union[Path, bytes, BinaryIO],
        tables: List[ExtractedTable],
        base_filename: str = "table"
    ) -> List[ExportedTable]:
        """
        Exportiert mehrere Tabellen als separate PDFs.
        
        Args:
            source_pdf: Quell-PDF
            tables: Liste von ExtractedTable
            base_filename: Basis für Dateinamen
            
        Returns:
            Liste von ExportedTable
        """
        # PDF einmal öffnen für alle Exports
        doc = self._open_document(source_pdf)
        
        results = []
        try:
            for table in tables:
                # Überspringe Continuations
                if table.is_continuation:
                    continue
                
                start_page, end_page = table.page_range
                
                # Neues PDF erstellen
                new_doc = fitz.open()
                
                for page_num in range(start_page - 1, end_page):
                    if page_num < len(doc):
                        new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
                
                if self.crop_to_table and table.bbox and len(new_doc) == 1:
                    self._crop_page_to_bbox(new_doc[0], table.bbox)
                
                pdf_bytes = new_doc.tobytes()
                new_doc.close()
                
                # Dateiname
                if start_page == end_page:
                    filename = f"{base_filename}_{table.table_id}_page_{start_page}.pdf"
                else:
                    filename = f"{base_filename}_{table.table_id}_pages_{start_page}-{end_page}.pdf"
                
                results.append(ExportedTable(
                    table_id=table.table_id,
                    filename=filename,
                    start_page=start_page,
                    end_page=end_page,
                    pdf_bytes=pdf_bytes,
                    page_count=end_page - start_page + 1
                ))
                
        finally:
            doc.close()
        
        return results
    
    def export_tables_as_zip(
        self,
        source_pdf: Union[Path, bytes, BinaryIO],
        tables: List[ExtractedTable],
        base_filename: str = "table"
    ) -> bytes:
        """
        Exportiert mehrere Tabellen als ZIP-Archiv.
        
        Args:
            source_pdf: Quell-PDF
            tables: Liste von ExtractedTable
            base_filename: Basis für Dateinamen
            
        Returns:
            ZIP-Archiv als Bytes
        """
        exported = self.export_tables(source_pdf, tables, base_filename)
        
        # ZIP erstellen
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for exp in exported:
                zf.writestr(exp.filename, exp.pdf_bytes)
        
        return zip_buffer.getvalue()
    
    def export_page_range(
        self,
        source_pdf: Union[Path, bytes, BinaryIO],
        start_page: int,
        end_page: int,
        output_filename: Optional[str] = None
    ) -> bytes:
        """
        Exportiert einen beliebigen Seiten-Bereich.
        
        Args:
            source_pdf: Quell-PDF
            start_page: Erste Seite (1-basiert)
            end_page: Letzte Seite (1-basiert)
            output_filename: Optionaler Dateiname
            
        Returns:
            PDF als Bytes
        """
        doc = self._open_document(source_pdf)
        
        try:
            new_doc = fitz.open()
            
            for page_num in range(start_page - 1, end_page):
                if page_num < len(doc):
                    new_doc.insert_pdf(doc, from_page=page_num, to_page=page_num)
            
            pdf_bytes = new_doc.tobytes()
            new_doc.close()
            
            return pdf_bytes
            
        finally:
            doc.close()
    
    def _open_document(self, source: Union[Path, bytes, BinaryIO]) -> "fitz.Document":
        """Öffnet ein PDF aus verschiedenen Quellen."""
        if isinstance(source, bytes):
            return fitz.open(stream=source, filetype="pdf")
        elif isinstance(source, (str, Path)):
            return fitz.open(source)
        else:
            # File-like object
            return fitz.open(stream=source.read(), filetype="pdf")
    
    def _crop_page_to_bbox(self, page: "fitz.Page", bbox: tuple) -> None:
        """
        Schneidet eine Seite auf den Tabellen-Bereich zu.
        
        Args:
            page: PyMuPDF Page Objekt
            bbox: (x0, y0, x1, y1) Bounding Box
        """
        if len(bbox) == 4:
            # Etwas Padding hinzufügen
            padding = 10
            x0, y0, x1, y1 = bbox
            crop_rect = fitz.Rect(
                max(0, x0 - padding),
                max(0, y0 - padding),
                x1 + padding,
                y1 + padding
            )
            page.set_cropbox(crop_rect)


def create_table_export_summary(exports: List[ExportedTable]) -> str:
    """
    Erstellt eine Zusammenfassung der exportierten Tabellen.
    
    Returns:
        Formatierter String
    """
    lines = [f"📦 {len(exports)} Tabellen exportiert:"]
    total_size = 0
    
    for exp in exports:
        total_size += len(exp.pdf_bytes)
        page_info = f"S.{exp.start_page}" if exp.start_page == exp.end_page else f"S.{exp.start_page}-{exp.end_page}"
        lines.append(f"  • T{exp.table_id}: {exp.filename} ({page_info}, {exp.size_kb:.1f} KB)")
    
    lines.append(f"  Gesamt: {total_size/1024:.1f} KB")
    return "\n".join(lines)
