"""
Ground Truth Schema für Benchmarks.
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class DocumentGroundTruth:
    """Ground Truth für ein PDF."""
    file_name: str
    table_count: int
    image_count: int
    pages: int = 0
    category: str = "general"
    difficulty: int = 1
    notes: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "DocumentGroundTruth":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class GroundTruthManifest:
    """Sammlung aller Ground Truth Einträge."""
    documents: list[DocumentGroundTruth] = field(default_factory=list)
    
    def save(self, path: Path) -> None:
        data = {"documents": [d.to_dict() for d in self.documents]}
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    
    @classmethod
    def load(cls, path: Path) -> "GroundTruthManifest":
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(documents=[DocumentGroundTruth.from_dict(d) for d in data.get("documents", [])])
    
    def get(self, file_name: str) -> Optional[DocumentGroundTruth]:
        for doc in self.documents:
            if doc.file_name == file_name:
                return doc
        return None
    
    def add(self, doc: DocumentGroundTruth) -> None:
        existing = self.get(doc.file_name)
        if existing:
            self.documents.remove(existing)
        self.documents.append(doc)
    
    def remove(self, file_name: str) -> bool:
        existing = self.get(file_name)
        if existing:
            self.documents.remove(existing)
            return True
        return False
