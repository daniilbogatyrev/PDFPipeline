"""
CSV Benchmark Runner.
Vergleicht extrahierte Tabellen-Daten gegen Ground Truth CSVs.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
import time
import re

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.extractors import BaseExtractor, get_available_csv_extractors
from .csv_ground_truth import CSVGroundTruth, CSVGroundTruthManifest


@dataclass
class CellComparisonResult:
    """Vergleich einer einzelnen Zelle."""
    row: int
    col: int
    expected: Any
    actual: Any
    match: bool
    match_type: str  # "exact", "normalized", "numeric", "empty", "mismatch"


@dataclass
class TableComparisonResult:
    """Detaillierter Vergleich einer Tabelle."""
    table_id: int
    tool_name: str
    file_name: str
    
    # Struktur
    expected_rows: int
    expected_cols: int
    actual_rows: int
    actual_cols: int
    
    # Zellen-Vergleich
    total_cells: int = 0
    matched_cells: int = 0
    exact_matches: int = 0
    normalized_matches: int = 0  # Match nach Normalisierung (Whitespace, Case)
    numeric_matches: int = 0     # Numerisch gleich (1.0 == 1)
    empty_matches: int = 0       # Beide leer
    mismatches: int = 0
    
    # Details
    cell_comparisons: List[CellComparisonResult] = field(default_factory=list)
    mismatched_cells: List[CellComparisonResult] = field(default_factory=list)
    
    # Header
    header_match: bool = False
    
    # Timing
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    
    @property
    def success(self) -> bool:
        return self.error is None
    
    @property
    def structure_match(self) -> bool:
        """Stimmt die Struktur (Zeilen/Spalten) überein?"""
        return self.expected_rows == self.actual_rows and self.expected_cols == self.actual_cols
    
    @property
    def cell_accuracy(self) -> float:
        """Anteil korrekt extrahierter Zellen."""
        if self.total_cells == 0:
            return 0.0
        return self.matched_cells / self.total_cells
    
    @property
    def exact_accuracy(self) -> float:
        """Anteil exakt übereinstimmender Zellen."""
        if self.total_cells == 0:
            return 0.0
        return self.exact_matches / self.total_cells
    
    def to_dict(self) -> dict:
        return {
            "table_id": self.table_id,
            "tool": self.tool_name,
            "file": self.file_name,
            "structure": "✓" if self.structure_match else f"{self.actual_rows}x{self.actual_cols}",
            "expected": f"{self.expected_rows}x{self.expected_cols}",
            "cells": self.total_cells,
            "matched": self.matched_cells,
            "accuracy": f"{self.cell_accuracy:.1%}",
            "exact": f"{self.exact_accuracy:.1%}",
            "mismatches": self.mismatches,
            "header": "✓" if self.header_match else "✗",
            "time_ms": round(self.execution_time_ms, 1),
            "status": "✓" if self.cell_accuracy >= 0.95 else ("⚠" if self.cell_accuracy >= 0.8 else "✗")
        }


@dataclass
class CSVToolMetrics:
    """Aggregierte Metriken für ein Tool."""
    tool_name: str
    total_tables: int = 0
    successful_extractions: int = 0
    
    # Struktur
    structure_matches: int = 0
    
    # Zellen
    total_cells: int = 0
    total_matched: int = 0
    total_exact: int = 0
    total_mismatches: int = 0
    
    # Header
    header_matches: int = 0
    
    # Timing
    total_time_ms: float = 0.0
    
    @property
    def success_rate(self) -> float:
        if self.total_tables == 0:
            return 0.0
        return self.successful_extractions / self.total_tables
    
    @property
    def structure_accuracy(self) -> float:
        if self.successful_extractions == 0:
            return 0.0
        return self.structure_matches / self.successful_extractions
    
    @property
    def cell_accuracy(self) -> float:
        if self.total_cells == 0:
            return 0.0
        return self.total_matched / self.total_cells
    
    @property
    def exact_accuracy(self) -> float:
        if self.total_cells == 0:
            return 0.0
        return self.total_exact / self.total_cells
    
    @property
    def header_accuracy(self) -> float:
        if self.successful_extractions == 0:
            return 0.0
        return self.header_matches / self.successful_extractions
    
    @property
    def avg_time_ms(self) -> float:
        if self.successful_extractions == 0:
            return 0.0
        return self.total_time_ms / self.successful_extractions
    
    def to_dict(self) -> dict:
        return {
            "Tool": self.tool_name,
            "Erfolg": f"{self.success_rate:.0%}",
            "Struktur": f"{self.structure_accuracy:.0%}",
            "Zellen": f"{self.cell_accuracy:.1%}",
            "Exakt": f"{self.exact_accuracy:.1%}",
            "Header": f"{self.header_accuracy:.0%}",
            "Fehler": self.total_mismatches,
            "Ø Zeit": f"{self.avg_time_ms:.0f}ms"
        }


@dataclass
class CSVBenchmarkResult:
    """Gesamtergebnis eines CSV-Benchmarks."""
    tool_metrics: Dict[str, CSVToolMetrics] = field(default_factory=dict)
    table_comparisons: List[TableComparisonResult] = field(default_factory=list)
    
    def get_ranking(self, metric: str = "cell_accuracy") -> List[Tuple[str, float]]:
        """Ranking der Tools nach einer Metrik."""
        ranking = []
        for name, m in self.tool_metrics.items():
            value = getattr(m, metric, 0)
            ranking.append((name, value))
        
        reverse = metric != "avg_time_ms"
        return sorted(ranking, key=lambda x: x[1], reverse=reverse)
    
    def to_summary_list(self) -> List[dict]:
        """Für DataFrame-Anzeige."""
        return [m.to_dict() for m in self.tool_metrics.values()]
    
    def to_detailed_list(self) -> List[dict]:
        """Detaillierte Ergebnisse pro Tabelle."""
        return [t.to_dict() for t in self.table_comparisons]
    
    def get_comparisons_for_file(self, file_name: str) -> List[TableComparisonResult]:
        """Alle Vergleiche für eine Datei."""
        return [c for c in self.table_comparisons if c.file_name == file_name]
    
    def get_comparisons_for_tool(self, tool_name: str) -> List[TableComparisonResult]:
        """Alle Vergleiche für ein Tool."""
        return [c for c in self.table_comparisons if c.tool_name == tool_name]
    
    def get_best_tool_for_table(self, file_name: str, table_id: int) -> Optional[str]:
        """Findet das beste Tool für eine spezifische Tabelle."""
        relevant = [
            c for c in self.table_comparisons 
            if c.file_name == file_name and c.table_id == table_id and c.success
        ]
        if not relevant:
            return None
        
        best = max(relevant, key=lambda x: x.cell_accuracy)
        return best.tool_name


class CSVBenchmarkRunner:
    """
    Führt CSV-Benchmarks durch.
    
    Vergleicht extrahierte Tabellen-Daten mit Ground Truth CSVs.
    """
    
    def __init__(
        self,
        manifest: Optional[CSVGroundTruthManifest] = None,
        extractors: Optional[List[BaseExtractor]] = None,
        normalize_whitespace: bool = True,
        case_insensitive: bool = False,
        numeric_tolerance: float = 0.001
    ):
        """
        Args:
            manifest: CSV Ground Truth Manifest
            extractors: Liste von Extraktoren (default: alle verfügbaren)
            normalize_whitespace: Whitespace beim Vergleich normalisieren
            case_insensitive: Groß-/Kleinschreibung ignorieren
            numeric_tolerance: Toleranz für numerische Vergleiche
        """
        self.manifest = manifest
        self.extractors = extractors or get_available_csv_extractors()
        self.normalize_whitespace = normalize_whitespace
        self.case_insensitive = case_insensitive
        self.numeric_tolerance = numeric_tolerance
    
    def run(self, files: List[Tuple[str, bytes]]) -> CSVBenchmarkResult:
        """
        Führt den Benchmark durch.
        
        Args:
            files: Liste von (filename, pdf_bytes) Tupeln
            
        Returns:
            CSVBenchmarkResult mit allen Metriken
        """
        result = CSVBenchmarkResult()
        
        # Initialisiere Metriken für alle Tools
        for ext in self.extractors:
            result.tool_metrics[ext.name] = CSVToolMetrics(tool_name=ext.name)
        
        for filename, file_bytes in files:
            # Hole Ground Truth für diese Datei
            gt_tables = self.manifest.get_all_for_file(filename) if self.manifest else []
            
            if not gt_tables:
                continue
            
            # Extrahiere mit jedem Tool
            for extractor in self.extractors:
                metrics = result.tool_metrics[extractor.name]
                
                start_time = time.perf_counter()
                
                try:
                    extraction = extractor.extract(file_bytes, filename)
                    extraction_time = (time.perf_counter() - start_time) * 1000
                    
                    if not extraction.success:
                        # Fehlgeschlagene Extraktion
                        for gt in gt_tables:
                            metrics.total_tables += 1
                            result.table_comparisons.append(TableComparisonResult(
                                table_id=gt.table_id,
                                tool_name=extractor.name,
                                file_name=filename,
                                expected_rows=gt.rows,
                                expected_cols=gt.cols,
                                actual_rows=0,
                                actual_cols=0,
                                error=extraction.error
                            ))
                        continue
                    
                    # Vergleiche jede Ground Truth Tabelle
                    for gt in gt_tables:
                        metrics.total_tables += 1
                        
                        # Finde passende extrahierte Tabelle
                        extracted_table = extraction.get_table_by_id(gt.table_id)
                        
                        if not extracted_table or not extracted_table.has_data:
                            result.table_comparisons.append(TableComparisonResult(
                                table_id=gt.table_id,
                                tool_name=extractor.name,
                                file_name=filename,
                                expected_rows=gt.rows,
                                expected_cols=gt.cols,
                                actual_rows=0,
                                actual_cols=0,
                                error=f"Tabelle {gt.table_id} nicht gefunden oder keine Daten"
                            ))
                            continue
                        
                        # Vergleiche Tabellen
                        comparison = self._compare_tables(
                            gt, 
                            extracted_table, 
                            extractor.name,
                            filename
                        )
                        comparison.execution_time_ms = extraction_time
                        
                        # Update Metriken
                        metrics.successful_extractions += 1
                        metrics.total_time_ms += extraction_time
                        
                        if comparison.structure_match:
                            metrics.structure_matches += 1
                        
                        if comparison.header_match:
                            metrics.header_matches += 1
                        
                        metrics.total_cells += comparison.total_cells
                        metrics.total_matched += comparison.matched_cells
                        metrics.total_exact += comparison.exact_matches
                        metrics.total_mismatches += comparison.mismatches
                        
                        result.table_comparisons.append(comparison)
                        
                except Exception as e:
                    for gt in gt_tables:
                        metrics.total_tables += 1
                        result.table_comparisons.append(TableComparisonResult(
                            table_id=gt.table_id,
                            tool_name=extractor.name,
                            file_name=filename,
                            expected_rows=gt.rows,
                            expected_cols=gt.cols,
                            actual_rows=0,
                            actual_cols=0,
                            error=str(e)
                        ))
        
        return result
    
    def _compare_tables(
        self,
        gt: CSVGroundTruth,
        extracted: "ExtractedTable",
        tool_name: str,
        file_name: str
    ) -> TableComparisonResult:
        """Vergleicht eine extrahierte Tabelle mit Ground Truth."""
        
        # Hole DataFrames
        try:
            gt_df = gt.dataframe
            ext_df = extracted.to_dataframe()
        except Exception as e:
            return TableComparisonResult(
                table_id=gt.table_id,
                tool_name=tool_name,
                file_name=file_name,
                expected_rows=gt.rows,
                expected_cols=gt.cols,
                actual_rows=0,
                actual_cols=0,
                error=f"DataFrame-Konvertierung fehlgeschlagen: {e}"
            )
        
        result = TableComparisonResult(
            table_id=gt.table_id,
            tool_name=tool_name,
            file_name=file_name,
            expected_rows=len(gt_df),
            expected_cols=len(gt_df.columns),
            actual_rows=len(ext_df),
            actual_cols=len(ext_df.columns)
        )
        
        # Header-Vergleich
        if gt.has_header and len(gt_df.columns) > 0 and len(ext_df.columns) > 0:
            gt_headers = [self._normalize(str(c)) for c in gt_df.columns]
            ext_headers = [self._normalize(str(c)) for c in ext_df.columns]
            result.header_match = gt_headers == ext_headers
        
        # Zellen-Vergleich
        # Verwende die kleinere Dimension
        rows_to_compare = min(len(gt_df), len(ext_df))
        cols_to_compare = min(len(gt_df.columns), len(ext_df.columns))
        
        result.total_cells = len(gt_df) * len(gt_df.columns)
        
        for row in range(rows_to_compare):
            for col in range(cols_to_compare):
                try:
                    gt_val = gt_df.iloc[row, col]
                    ext_val = ext_df.iloc[row, col]
                    
                    match, match_type = self._compare_cells(gt_val, ext_val)
                    
                    cell_result = CellComparisonResult(
                        row=row,
                        col=col,
                        expected=gt_val,
                        actual=ext_val,
                        match=match,
                        match_type=match_type
                    )
                    
                    if match:
                        result.matched_cells += 1
                        if match_type == "exact":
                            result.exact_matches += 1
                        elif match_type == "normalized":
                            result.normalized_matches += 1
                        elif match_type == "numeric":
                            result.numeric_matches += 1
                        elif match_type == "empty":
                            result.empty_matches += 1
                    else:
                        result.mismatches += 1
                        result.mismatched_cells.append(cell_result)
                    
                    result.cell_comparisons.append(cell_result)
                    
                except Exception:
                    result.mismatches += 1
        
        # Zusätzliche Zellen in GT die nicht verglichen wurden
        if len(gt_df) > rows_to_compare or len(gt_df.columns) > cols_to_compare:
            extra_cells = (len(gt_df) * len(gt_df.columns)) - (rows_to_compare * cols_to_compare)
            result.mismatches += extra_cells
        
        return result
    
    def _compare_cells(self, expected: Any, actual: Any) -> Tuple[bool, str]:
        """
        Vergleicht zwei Zellen-Werte.
        
        Returns:
            (match: bool, match_type: str)
        """
        # None/NaN handling
        exp_empty = pd.isna(expected) or str(expected).strip() == ""
        act_empty = pd.isna(actual) or str(actual).strip() == ""
        
        if exp_empty and act_empty:
            return True, "empty"
        
        if exp_empty != act_empty:
            return False, "mismatch"
        
        # String-Konvertierung
        exp_str = str(expected)
        act_str = str(actual)
        
        # Exakter Match
        if exp_str == act_str:
            return True, "exact"
        
        # Normalisierter Match
        exp_norm = self._normalize(exp_str)
        act_norm = self._normalize(act_str)
        
        if exp_norm == act_norm:
            return True, "normalized"
        
        # Numerischer Match
        try:
            exp_num = self._parse_number(exp_str)
            act_num = self._parse_number(act_str)
            
            if exp_num is not None and act_num is not None:
                if abs(exp_num - act_num) <= self.numeric_tolerance:
                    return True, "numeric"
                # Prozentuale Toleranz für größere Zahlen
                if exp_num != 0 and abs((exp_num - act_num) / exp_num) <= self.numeric_tolerance:
                    return True, "numeric"
        except Exception:
            pass
        
        return False, "mismatch"
    
    def _normalize(self, value: str) -> str:
        """Normalisiert einen String für Vergleich."""
        result = value
        
        if self.normalize_whitespace:
            result = " ".join(result.split())
        
        if self.case_insensitive:
            result = result.lower()
        
        return result.strip()
    
    def _parse_number(self, value: str) -> Optional[float]:
        """Versucht einen String als Zahl zu parsen."""
        if not value:
            return None
        
        # Entferne Währungssymbole und Tausender-Trennzeichen
        cleaned = re.sub(r'[€$£¥\s]', '', value)
        
        # Deutsche Zahlenformat: 1.234,56 -> 1234.56
        if ',' in cleaned and '.' in cleaned:
            if cleaned.rfind(',') > cleaned.rfind('.'):
                cleaned = cleaned.replace('.', '').replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')
        
        try:
            return float(cleaned)
        except ValueError:
            return None


def create_csv_comparison_report(comparison: TableComparisonResult) -> str:
    """Erstellt einen detaillierten Text-Report für einen Tabellen-Vergleich."""
    lines = [
        f"=== CSV Vergleich: Tabelle {comparison.table_id} ===",
        f"Tool: {comparison.tool_name}",
        f"Datei: {comparison.file_name}",
        "",
        f"Struktur: {comparison.expected_rows}x{comparison.expected_cols} erwartet, "
        f"{comparison.actual_rows}x{comparison.actual_cols} extrahiert "
        f"{'✓' if comparison.structure_match else '✗'}",
        "",
        f"Zellen-Genauigkeit: {comparison.cell_accuracy:.1%}",
        f"  - Exakt: {comparison.exact_matches}",
        f"  - Normalisiert: {comparison.normalized_matches}",
        f"  - Numerisch: {comparison.numeric_matches}",
        f"  - Leer: {comparison.empty_matches}",
        f"  - Fehler: {comparison.mismatches}",
        "",
        f"Header: {'✓' if comparison.header_match else '✗'}",
        f"Zeit: {comparison.execution_time_ms:.1f}ms",
    ]
    
    if comparison.mismatched_cells:
        lines.append("")
        lines.append("Fehlerhafte Zellen (max. 10):")
        for cell in comparison.mismatched_cells[:10]:
            lines.append(f"  [{cell.row},{cell.col}]: '{cell.expected}' != '{cell.actual}'")
    
    return "\n".join(lines)
