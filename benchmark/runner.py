"""
Benchmark Runner.
Vergleicht Extraktoren gegen Ground Truth.
"""

from dataclasses import dataclass, field
from typing import Optional
import sys
import os

# Füge parent directory zum Path hinzu
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.extractors import BaseExtractor, get_available_extractors
from .ground_truth import GroundTruthManifest, DocumentGroundTruth


@dataclass
class ToolMetrics:
    """Metriken für ein Tool."""
    tool_name: str
    total_files: int = 0
    successful: int = 0
    table_exact: int = 0
    table_over: int = 0
    table_under: int = 0
    image_exact: int = 0
    total_time_ms: float = 0.0
    
    @property
    def table_accuracy(self) -> float:
        return self.table_exact / self.total_files if self.total_files > 0 else 0.0
    
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
            "Bilder ✓": f"{self.image_accuracy:.0%}",
            "Überzählt": self.table_over,
            "Unterzählt": self.table_under,
            "Ø Zeit": f"{self.avg_time_ms:.0f}ms",
        }


@dataclass
class BenchmarkResult:
    """Ergebnis eines Benchmark-Laufs."""
    tool_metrics: dict[str, ToolMetrics] = field(default_factory=dict)
    detailed_results: list[dict] = field(default_factory=list)
    
    def get_ranking(self, metric: str = "table_accuracy") -> list[tuple[str, float]]:
        ranking = [(name, getattr(m, metric, 0)) for name, m in self.tool_metrics.items()]
        reverse = metric != "avg_time_ms"
        return sorted(ranking, key=lambda x: x[1], reverse=reverse)
    
    def to_summary_list(self) -> list[dict]:
        """Für DataFrame."""
        return [m.to_dict() for m in self.tool_metrics.values()]


class BenchmarkRunner:
    """Führt Benchmarks aus."""
    
    def __init__(
        self,
        manifest: Optional[GroundTruthManifest] = None,
        extractors: Optional[list[BaseExtractor]] = None
    ):
        self.manifest = manifest
        self.extractors = extractors or get_available_extractors()
    
    def run(self, files: list[tuple[str, bytes]]) -> BenchmarkResult:
        """
        Führt Benchmark auf Dateien aus.
        
        Args:
            files: Liste von (filename, bytes) Tupeln
        """
        result = BenchmarkResult()
        
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
                    
                    detail = {
                        "file": filename,
                        "tool": extractor.name,
                        "tables": extraction.table_count,
                        "images": extraction.image_count,
                        "pages": extraction.pages,
                        "time_ms": round(extraction.execution_time_ms, 1),
                        "gt_tables": gt.table_count if gt else None,
                        "gt_images": gt.image_count if gt else None,
                        "table_diff": None,
                        "image_diff": None,
                        "status": "○"
                    }
                    
                    if gt:
                        table_diff = extraction.table_count - gt.table_count
                        image_diff = extraction.image_count - gt.image_count
                        
                        detail["table_diff"] = table_diff
                        detail["image_diff"] = image_diff
                        
                        if table_diff == 0:
                            metrics.table_exact += 1
                            detail["status"] = "✓"
                        elif table_diff > 0:
                            metrics.table_over += 1
                            detail["status"] = "↑"
                        else:
                            metrics.table_under += 1
                            detail["status"] = "↓"
                        
                        if image_diff == 0:
                            metrics.image_exact += 1
                    
                    result.detailed_results.append(detail)
        
        return result
