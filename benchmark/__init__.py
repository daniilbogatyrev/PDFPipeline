"""
Benchmark Package.

Enthält:
- Ground Truth Schema mit detaillierten Tabellen-Definitionen
- Benchmark Runner für Tool-Vergleiche
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

__all__ = [
    # Ground Truth
    "GroundTruthManifest",
    "DocumentGroundTruth",
    "TableDefinition",
    
    # Runner & Results
    "BenchmarkRunner",
    "BenchmarkResult",
    "ToolMetrics",
    "DetailedTableReport",
    "TableComparisonResult",
]
