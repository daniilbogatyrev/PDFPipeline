"""
Benchmark Runner.
Vergleicht Extraktoren gegen Ground Truth mit detailliertem Tabellen-Report.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Set
import sys
import os

# Füge parent directory zum Path hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.extractors import BaseExtractor, ExtractionResult, ExtractedTable, get_available_extractors
from .ground_truth import GroundTruthManifest, DocumentGroundTruth, TableDefinition


@dataclass
class TableComparisonResult:
    """Vergleich einer einzelnen Tabelle zwischen Extraction und Ground Truth."""
    table_id: int
    gt_pages: tuple[int, int]  # (start, end) aus Ground Truth
    extracted_pages: Optional[tuple[int, int]]  # (start, end) aus Extraktion, None wenn nicht gefunden
    match_status: str  # "exact", "partial", "missing", "extra"
    
    @property
    def gt_page_str(self) -> str:
        if self.gt_pages[0] == self.gt_pages[1]:
            return f"S.{self.gt_pages[0]}"
        return f"S.{self.gt_pages[0]}-{self.gt_pages[1]}"
    
    @property
    def extracted_page_str(self) -> str:
        if not self.extracted_pages:
            return "-"
        if self.extracted_pages[0] == self.extracted_pages[1]:
            return f"S.{self.extracted_pages[0]}"
        return f"S.{self.extracted_pages[0]}-{self.extracted_pages[1]}"


@dataclass
class ToolMetrics:
    """Metriken für ein Tool - erweitert um Seiten-Genauigkeit."""
    tool_name: str
    total_files: int = 0
    successful: int = 0
    
    # Tabellen-Metriken (Anzahl)
    table_exact: int = 0
    table_over: int = 0
    table_under: int = 0
    
    # Tabellen-Metriken (Seiten-Zuordnung)
    table_page_exact: int = 0  # Richtige Seite
    table_page_partial: int = 0  # Teilweise richtig (bei spanning)
    
    # Spanning-Metriken
    spanning_detected: int = 0
    spanning_total_gt: int = 0
    
    # Bild-Metriken
    image_exact: int = 0
    
    total_time_ms: float = 0.0
    
    @property
    def table_accuracy(self) -> float:
        """Genauigkeit der Tabellen-Anzahl."""
        return self.table_exact / self.total_files if self.total_files > 0 else 0.0
    
    @property
    def table_page_accuracy(self) -> float:
        """Genauigkeit der Seiten-Zuordnung."""
        total = self.table_page_exact + self.table_page_partial
        expected = self.table_exact * self.total_files  # Rough estimate
        return total / max(expected, 1)
    
    @property
    def spanning_recall(self) -> float:
        """Wie viele spanning tables wurden erkannt."""
        return self.spanning_detected / self.spanning_total_gt if self.spanning_total_gt > 0 else 1.0
    
    @property
    def image_accuracy(self) -> float:
        return self.image_exact / self.total_files if self.total_files > 0 else 0.0
    
    @property
    def avg_time_ms(self) -> float:
        return self.total_time_ms / self.successful if self.successful > 0 else 0.0
    
    def to_dict(self) -> dict:
        return {
            "Tool": self.tool_name,
            "Tabellen ✓": f"{self.table_accuracy:.0%}",
            "Seiten ✓": f"{self.table_page_accuracy:.0%}",
            "Spanning": f"{self.spanning_detected}/{self.spanning_total_gt}",
            "Bilder ✓": f"{self.image_accuracy:.0%}",
            "Überzählt": self.table_over,
            "Unterzählt": self.table_under,
            "Ø Zeit": f"{self.avg_time_ms:.0f}ms",
        }


@dataclass
class DetailedTableReport:
    """Detaillierter Report pro Datei und Tool."""
    file_name: str
    tool_name: str
    
    # Ground Truth
    gt_table_count: int
    gt_tables: List[TableDefinition]
    
    # Extraction
    extracted_count: int
    extracted_tables: List[ExtractedTable]
    
    # Vergleich
    comparisons: List[TableComparisonResult] = field(default_factory=list)
    
    @property
    def count_diff(self) -> int:
        return self.extracted_count - self.gt_table_count
    
    @property
    def gt_summary(self) -> str:
        """z.B. '4 Tabellen: T1(S.1-4), T2(S.5), T3(S.6), T4(S.6)'"""
        if not self.gt_tables:
            return f"{self.gt_table_count} Tabellen"
        parts = [f"T{t.table_id}({t.page_range_str})" for t in self.gt_tables]
        return f"{self.gt_table_count} Tabellen: {', '.join(parts)}"
    
    @property
    def extracted_summary(self) -> str:
        """z.B. '3 Tabellen: T1(S.1), T2(S.2), T3(S.5)'"""
        if not self.extracted_tables:
            return f"{self.extracted_count} Tabellen"
        # Nur Haupt-Tabellen (nicht Continuations)
        main = [t for t in self.extracted_tables if not t.is_continuation]
        parts = [f"T{t.table_id}({t.page_range_str})" for t in main]
        return f"{len(main)} Tabellen: {', '.join(parts)}"
    
    def to_dict(self) -> dict:
        return {
            "file": self.file_name,
            "tool": self.tool_name,
            "gt_count": self.gt_table_count,
            "gt_detail": self.gt_summary,
            "extracted_count": self.extracted_count,
            "extracted_detail": self.extracted_summary,
            "diff": self.count_diff,
            "status": "✓" if self.count_diff == 0 else ("↑" if self.count_diff > 0 else "↓")
        }


@dataclass
class BenchmarkResult:
    """Ergebnis eines Benchmark-Laufs mit detaillierten Reports."""
    tool_metrics: Dict[str, ToolMetrics] = field(default_factory=dict)
    detailed_results: List[dict] = field(default_factory=list)
    table_reports: List[DetailedTableReport] = field(default_factory=list)
    
    def get_ranking(self, metric: str = "table_accuracy") -> List[tuple[str, float]]:
        ranking = [(name, getattr(m, metric, 0)) for name, m in self.tool_metrics.items()]
        reverse = metric != "avg_time_ms"
        return sorted(ranking, key=lambda x: x[1], reverse=reverse)
    
    def to_summary_list(self) -> List[dict]:
        """Für DataFrame."""
        return [m.to_dict() for m in self.tool_metrics.values()]
    
    def get_table_reports_for_file(self, file_name: str) -> List[DetailedTableReport]:
        """Alle Tool-Reports für eine Datei."""
        return [r for r in self.table_reports if r.file_name == file_name]
    
    def to_detailed_table_list(self) -> List[dict]:
        """Detaillierte Tabellen-Reports für DataFrame."""
        return [r.to_dict() for r in self.table_reports]


class BenchmarkRunner:
    """Führt Benchmarks mit detailliertem Tabellen-Vergleich aus."""
    
    def __init__(
        self,
        manifest: Optional[GroundTruthManifest] = None,
        extractors: Optional[List[BaseExtractor]] = None
    ):
        self.manifest = manifest
        self.extractors = extractors or get_available_extractors()
    
    def run(self, files: List[tuple[str, bytes]]) -> BenchmarkResult:
        """
        Führt Benchmark auf Dateien aus.
        
        Args:
            files: Liste von (filename, bytes) Tupeln
            
        Returns:
            BenchmarkResult mit allen Metriken und Details
        """
        result = BenchmarkResult()
        
        # Initialisiere Metriken für alle Tools
        for ext in self.extractors:
            result.tool_metrics[ext.name] = ToolMetrics(tool_name=ext.name)
        
        for filename, file_bytes in files:
            gt = self.manifest.get(filename) if self.manifest else None
            
            for extractor in self.extractors:
                metrics = result.tool_metrics[extractor.name]
                metrics.total_files += 1
                
                extraction = extractor.extract(file_bytes, filename)
                
                if extraction.success:
                    metrics.successful += 1
                    metrics.total_time_ms += extraction.execution_time_ms
                    
                    # Basis-Detail für alte Kompatibilität
                    detail = {
                        "file": filename,
                        "tool": extractor.name,
                        "tables": extraction.table_count,
                        "tables_summary": extraction.get_table_summary(),
                        "spanning": extraction.spanning_table_count,
                        "pages_with_tables": extraction.pages_with_tables,
                        "images": extraction.image_count,
                        "pages": extraction.pages,
                        "time_ms": round(extraction.execution_time_ms, 1),
                        "gt_tables": gt.table_count if gt else None,
                        "gt_images": gt.image_count if gt else None,
                        "table_diff": None,
                        "image_diff": None,
                        "status": "○"
                    }
                    
                    # Detaillierter Tabellen-Report
                    table_report = DetailedTableReport(
                        file_name=filename,
                        tool_name=extractor.name,
                        gt_table_count=gt.table_count if gt else 0,
                        gt_tables=gt.tables if gt else [],
                        extracted_count=extraction.table_count,
                        extracted_tables=extraction.tables
                    )
                    
                    if gt:
                        table_diff = extraction.table_count - gt.table_count
                        image_diff = extraction.image_count - gt.image_count
                        
                        detail["table_diff"] = table_diff
                        detail["image_diff"] = image_diff
                        detail["gt_tables_detail"] = table_report.gt_summary
                        
                        # Tabellen-Anzahl Metriken
                        if table_diff == 0:
                            metrics.table_exact += 1
                            detail["status"] = "✓"
                        elif table_diff > 0:
                            metrics.table_over += 1
                            detail["status"] = "↑"
                        else:
                            metrics.table_under += 1
                            detail["status"] = "↓"
                        
                        # Bild-Metriken
                        if image_diff == 0:
                            metrics.image_exact += 1
                        
                        # Spanning-Metriken
                        metrics.spanning_total_gt += gt.spanning_table_count
                        metrics.spanning_detected += extraction.spanning_table_count
                        
                        # Seiten-Vergleich (falls GT Details hat)
                        if gt.tables:
                            comparisons = self._compare_table_pages(gt.tables, extraction.tables)
                            table_report.comparisons = comparisons
                            
                            for comp in comparisons:
                                if comp.match_status == "exact":
                                    metrics.table_page_exact += 1
                                elif comp.match_status == "partial":
                                    metrics.table_page_partial += 1
                    
                    result.detailed_results.append(detail)
                    result.table_reports.append(table_report)
        
        return result
    
    def _compare_table_pages(
        self,
        gt_tables: List[TableDefinition],
        extracted_tables: List[ExtractedTable]
    ) -> List[TableComparisonResult]:
        """
        Vergleicht GT-Tabellen mit extrahierten Tabellen auf Seiten-Ebene.
        
        Matching-Strategie: 
        - Suche für jede GT-Tabelle eine passende extrahierte Tabelle
        - "exact" wenn Seiten-Range identisch
        - "partial" wenn Überlappung
        - "missing" wenn nicht gefunden
        """
        comparisons = []
        
        # Nur Haupt-Tabellen (nicht Continuations)
        main_extracted = [t for t in extracted_tables if not t.is_continuation]
        used_extracted: Set[int] = set()
        
        for gt_table in gt_tables:
            gt_range = (gt_table.start_page, gt_table.end_page)
            best_match = None
            best_status = "missing"
            
            for ext_table in main_extracted:
                if ext_table.table_id in used_extracted:
                    continue
                
                ext_range = ext_table.page_range
                
                # Exakte Übereinstimmung
                if ext_range == gt_range:
                    best_match = ext_table
                    best_status = "exact"
                    break
                
                # Teilweise Übereinstimmung (Überlappung)
                if self._ranges_overlap(gt_range, ext_range):
                    if best_status != "exact":
                        best_match = ext_table
                        best_status = "partial"
            
            if best_match:
                used_extracted.add(best_match.table_id)
            
            comparisons.append(TableComparisonResult(
                table_id=gt_table.table_id,
                gt_pages=gt_range,
                extracted_pages=best_match.page_range if best_match else None,
                match_status=best_status
            ))
        
        # Extra Tabellen (in Extraktion aber nicht in GT)
        for ext_table in main_extracted:
            if ext_table.table_id not in used_extracted:
                comparisons.append(TableComparisonResult(
                    table_id=ext_table.table_id,
                    gt_pages=(0, 0),
                    extracted_pages=ext_table.page_range,
                    match_status="extra"
                ))
        
        return comparisons
    
    def _ranges_overlap(self, range1: tuple[int, int], range2: tuple[int, int]) -> bool:
        """Prüft ob zwei Seiten-Ranges überlappen."""
        return range1[0] <= range2[1] and range2[0] <= range1[1]
