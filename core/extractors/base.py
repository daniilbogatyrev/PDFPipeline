"""
Base Extractor Interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union
import time


@dataclass
class ExtractionResult:
    """Einheitliches Ergebnis für alle Extraktoren."""
    tool_name: str
    file_path: str
    table_count: int = 0
    image_count: int = 0
    image_count_total: int = 0
    pages: int = 0
    paragraphs: int = 0
    math_formulas: int = 0
    tables_data: list = field(default_factory=list)
    execution_time_ms: float = 0.0
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        return self.error is None
    
    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "tables": self.table_count,
            "images": self.image_count,
            "images_total": self.image_count_total,
            "pages": self.pages,
            "paragraphs": self.paragraphs,
            "math_formulas": self.math_formulas,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }


class BaseExtractor(ABC):
    """Abstrakte Basisklasse für PDF-Extraktoren."""
    
    def __init__(self):
        self._name = self.__class__.__name__
    
    @property
    def name(self) -> str:
        return self._name
    
    @abstractmethod
    def is_available(self) -> bool:
        pass
    
    @abstractmethod
    def extract(self, source: Union[Path, bytes], filename: str = "") -> ExtractionResult:
        pass
