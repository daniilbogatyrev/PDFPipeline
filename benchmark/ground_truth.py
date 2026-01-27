"""
Ground Truth Schema für Benchmarks.
Erweitert um detaillierte Tabellen-Informationen (Seiten, Ranges).
"""

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List


@dataclass
class TableDefinition:
    """
    Definition einer einzelnen Tabelle in der Ground Truth.
    
    Attributes:
        table_id: Eindeutige ID der Tabelle (1-basiert)
        start_page: Erste Seite der Tabelle (1-basiert)
        end_page: Letzte Seite der Tabelle (1-basiert, gleich start_page wenn single-page)
        description: Optionale Beschreibung (z.B. "Haupttabelle", "Appendix A")
        is_spanning: True wenn Tabelle über mehrere Seiten geht
    """
    table_id: int
    start_page: int
    end_page: int = 0  # 0 = wird auf start_page gesetzt
    description: str = ""
    
    def __post_init__(self):
        if self.end_page == 0:
            self.end_page = self.start_page
    
    @property
    def is_spanning(self) -> bool:
        """Tabelle geht über mehrere Seiten."""
        return self.end_page > self.start_page
    
    @property
    def page_count(self) -> int:
        """Anzahl der Seiten die die Tabelle umfasst."""
        return self.end_page - self.start_page + 1
    
    @property
    def page_range_str(self) -> str:
        """Menschenlesbare Seiten-Angabe."""
        if self.is_spanning:
            return f"S.{self.start_page}-{self.end_page}"
        return f"S.{self.start_page}"
    
    def to_dict(self) -> dict:
        return {
            "table_id": self.table_id,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "TableDefinition":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class DocumentGroundTruth:
    """
    Ground Truth für ein PDF.
    
    Attributes:
        file_name: Name der PDF-Datei
        table_count: Gesamtzahl der logischen Tabellen
        tables: Detaillierte Liste der Tabellen mit Seiten-Info
        image_count: Anzahl unique Bilder
        pages: Gesamtseitenzahl des Dokuments
        category: Kategorie für Gruppierung im Benchmark
        difficulty: Schwierigkeitsgrad 1-5
        notes: Freitext-Notizen
    """
    file_name: str
    table_count: int = 0
    tables: List[TableDefinition] = field(default_factory=list)
    image_count: int = 0
    pages: int = 0
    category: str = "general"
    difficulty: int = 1
    notes: str = ""
    
    def __post_init__(self):
        # Synchronisiere table_count mit tables Liste falls vorhanden
        if self.tables and self.table_count == 0:
            self.table_count = len(self.tables)
    
    @property
    def spanning_table_count(self) -> int:
        """Anzahl der Tabellen die über mehrere Seiten gehen."""
        return sum(1 for t in self.tables if t.is_spanning)
    
    @property
    def tables_by_page(self) -> dict[int, List[TableDefinition]]:
        """Gruppiert Tabellen nach ihrer Start-Seite."""
        result = {}
        for table in self.tables:
            page = table.start_page
            if page not in result:
                result[page] = []
            result[page].append(table)
        return result
    
    @property
    def pages_with_tables(self) -> set[int]:
        """Alle Seiten auf denen Tabellen vorkommen."""
        pages = set()
        for table in self.tables:
            for p in range(table.start_page, table.end_page + 1):
                pages.add(p)
        return pages
    
    def add_table(self, start_page: int, end_page: int = 0, description: str = "") -> None:
        """Fügt eine Tabelle hinzu und aktualisiert den Zähler."""
        new_id = len(self.tables) + 1
        self.tables.append(TableDefinition(
            table_id=new_id,
            start_page=start_page,
            end_page=end_page or start_page,
            description=description
        ))
        self.table_count = len(self.tables)
    
    def to_dict(self) -> dict:
        return {
            "file_name": self.file_name,
            "table_count": self.table_count,
            "tables": [t.to_dict() for t in self.tables],
            "image_count": self.image_count,
            "pages": self.pages,
            "category": self.category,
            "difficulty": self.difficulty,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "DocumentGroundTruth":
        tables_data = data.pop("tables", [])
        tables = [TableDefinition.from_dict(t) for t in tables_data]
        
        # Filtere nur bekannte Felder
        known_fields = {f for f in cls.__dataclass_fields__ if f != "tables"}
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        
        return cls(tables=tables, **filtered_data)


@dataclass
class GroundTruthManifest:
    """Sammlung aller Ground Truth Einträge."""
    documents: List[DocumentGroundTruth] = field(default_factory=list)
    
    def save(self, path: Path) -> None:
        """Speichert das Manifest als JSON."""
        data = {
            "version": "2.0",
            "documents": [d.to_dict() for d in self.documents]
        }
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    
    @classmethod
    def load(cls, path: Path) -> "GroundTruthManifest":
        """Lädt ein Manifest aus JSON."""
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(documents=[DocumentGroundTruth.from_dict(d) for d in data.get("documents", [])])
    
    def get(self, file_name: str) -> Optional[DocumentGroundTruth]:
        """Findet einen Eintrag nach Dateiname."""
        for doc in self.documents:
            if doc.file_name == file_name:
                return doc
        return None
    
    def add(self, doc: DocumentGroundTruth) -> None:
        """Fügt einen Eintrag hinzu oder ersetzt existierenden."""
        existing = self.get(doc.file_name)
        if existing:
            self.documents.remove(existing)
        self.documents.append(doc)
    
    def remove(self, file_name: str) -> bool:
        """Entfernt einen Eintrag."""
        existing = self.get(file_name)
        if existing:
            self.documents.remove(existing)
            return True
        return False
    
    @property
    def total_tables(self) -> int:
        """Gesamtzahl aller Tabellen."""
        return sum(d.table_count for d in self.documents)
    
    @property
    def total_spanning_tables(self) -> int:
        """Gesamtzahl aller spanning Tabellen."""
        return sum(d.spanning_table_count for d in self.documents)
