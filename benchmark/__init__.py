"""
Benchmark Package.

Enthält:
- Ground Truth Schema mit detaillierten Tabellen-Definitionen
- Benchmark Runner für Tool-Vergleiche (Tabellen-Zählung)
- CSV Ground Truth und Benchmark (Tabellen-Inhalt)
- Metriken und Reports
"""

from .ground_truth import (
    GroundTruthManifest,
    DocumentGroundTruth,
    TableDefinition
)
from .runner import (
    BenchmarkRunner,
    BenchmarkResult,
    ToolMetrics,
    DetailedTableReport,
    TableComparisonResult
)
from .csv_ground_truth import (
    CSVGroundTruth,
    CSVGroundTruthManifest
)
from .csv_benchmark_runner import (
    CSVBenchmarkRunner,
    CSVBenchmarkResult,
    CSVToolMetrics,
    TableComparisonResult as CSVTableComparisonResult,
    CellComparisonResult,
    create_csv_comparison_report
)

__all__ = [
    # Ground Truth (Tabellen-Zählung)
    "GroundTruthManifest",
    "DocumentGroundTruth",
    "TableDefinition",
    
    # Runner & Results (Tabellen-Zählung)
    "BenchmarkRunner",
    "BenchmarkResult",
    "ToolMetrics",
    "DetailedTableReport",
    "TableComparisonResult",
    
    # CSV Ground Truth (Tabellen-Inhalt)
    "CSVGroundTruth",
    "CSVGroundTruthManifest",
    
    # CSV Benchmark Runner
    "CSVBenchmarkRunner",
    "CSVBenchmarkResult",
    "CSVToolMetrics",
    "CSVTableComparisonResult",
    "CellComparisonResult",
    "create_csv_comparison_report",
]
