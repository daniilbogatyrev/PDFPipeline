"""
CSV Ground Truth Schema.
Definiert erwartete Tabellen-Inhalte für Benchmark-Vergleiche.
"""

import json
import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Any, Dict

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


@dataclass
class CSVGroundTruth:
    """
    Ground Truth für eine einzelne Tabelle als CSV.
    
    Attributes:
        table_id: ID der Tabelle im Dokument (1-basiert)
        file_name: Zugehöriges PDF
        csv_data: CSV-String mit erwarteten Daten
        dataframe: Pandas DataFrame (lazy loaded)
        rows: Erwartete Zeilen-Anzahl (ohne Header)
        cols: Erwartete Spalten-Anzahl
        has_header: Ob die Tabelle einen Header hat
        notes: Anmerkungen zu Besonderheiten
    """
    table_id: int
    file_name: str
    csv_data: str = ""
    rows: int = 0
    cols: int = 0
    has_header: bool = True
    column_types: Dict[str, str] = field(default_factory=dict)  # Spalte -> Typ
    notes: str = ""
    
    _dataframe: Optional[Any] = field(default=None, repr=False)
    
    @property
    def dataframe(self) -> "pd.DataFrame":
        """Lazy-load DataFrame aus CSV-String."""
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas ist nicht installiert")
        
        if self._dataframe is None and self.csv_data:
            self._dataframe = pd.read_csv(
                io.StringIO(self.csv_data),
                header=0 if self.has_header else None
            )
        return self._dataframe
    
    @dataframe.setter
    def dataframe(self, df: "pd.DataFrame"):
        self._dataframe = df
        # Aktualisiere auch CSV-String
        self.csv_data = df.to_csv(index=False)
        self.rows = len(df)
        self.cols = len(df.columns)
    
    @property
    def cell_count(self) -> int:
        return self.rows * self.cols
    
    @property
    def column_names(self) -> List[str]:
        """Liste der Spaltennamen."""
        if self._dataframe is not None:
            return list(self._dataframe.columns)
        if self.csv_data and self.has_header:
            reader = csv.reader(io.StringIO(self.csv_data))
            return next(reader, [])
        return []
    
    def get_cell(self, row: int, col: int) -> Any:
        """Zugriff auf einzelne Zelle (0-basiert)."""
        df = self.dataframe
        if df is None or row >= len(df) or col >= len(df.columns):
            return None
        return df.iloc[row, col]
    
    def to_dict(self) -> dict:
        return {
            "table_id": self.table_id,
            "file_name": self.file_name,
            "csv_data": self.csv_data,
            "rows": self.rows,
            "cols": self.cols,
            "has_header": self.has_header,
            "column_types": self.column_types,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CSVGroundTruth":
        return cls(
            table_id=data.get("table_id", 0),
            file_name=data.get("file_name", ""),
            csv_data=data.get("csv_data", ""),
            rows=data.get("rows", 0),
            cols=data.get("cols", 0),
            has_header=data.get("has_header", True),
            column_types=data.get("column_types", {}),
            notes=data.get("notes", "")
        )
    
    @classmethod
    def from_csv_file(cls, csv_path: Path, table_id: int, file_name: str) -> "CSVGroundTruth":
        """Erstellt Ground Truth aus einer CSV-Datei."""
        csv_data = Path(csv_path).read_text(encoding='utf-8')
        
        df = pd.read_csv(io.StringIO(csv_data))
        
        return cls(
            table_id=table_id,
            file_name=file_name,
            csv_data=csv_data,
            rows=len(df),
            cols=len(df.columns),
            has_header=True
        )
    
    @classmethod
    def from_dataframe(cls, df: "pd.DataFrame", table_id: int, file_name: str) -> "CSVGroundTruth":
        """Erstellt Ground Truth aus einem DataFrame."""
        gt = cls(
            table_id=table_id,
            file_name=file_name,
            rows=len(df),
            cols=len(df.columns),
            has_header=True
        )
        gt.dataframe = df
        return gt


@dataclass
class CSVGroundTruthManifest:
    """
    Sammlung aller CSV Ground Truth Einträge.
    """
    tables: List[CSVGroundTruth] = field(default_factory=list)
    
    def save(self, path: Path) -> None:
        """Speichert das Manifest als JSON."""
        data = {
            "version": "1.0",
            "type": "csv_ground_truth",
            "tables": [t.to_dict() for t in self.tables]
        }
        Path(path).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), 
            encoding='utf-8'
        )
    
    @classmethod
    def load(cls, path: Path) -> "CSVGroundTruthManifest":
        """Lädt ein Manifest aus JSON."""
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        return cls(
            tables=[CSVGroundTruth.from_dict(t) for t in data.get("tables", [])]
        )
    
    def get(self, file_name: str, table_id: int) -> Optional[CSVGroundTruth]:
        """Findet einen Eintrag nach Dateiname und Tabellen-ID."""
        for table in self.tables:
            if table.file_name == file_name and table.table_id == table_id:
                return table
        return None
    
    def get_all_for_file(self, file_name: str) -> List[CSVGroundTruth]:
        """Alle Ground Truth Einträge für eine Datei."""
        return [t for t in self.tables if t.file_name == file_name]
    
    def add(self, table: CSVGroundTruth) -> None:
        """Fügt einen Eintrag hinzu oder ersetzt existierenden."""
        existing = self.get(table.file_name, table.table_id)
        if existing:
            self.tables.remove(existing)
        self.tables.append(table)
    
    def remove(self, file_name: str, table_id: int) -> bool:
        """Entfernt einen Eintrag."""
        existing = self.get(file_name, table_id)
        if existing:
            self.tables.remove(existing)
            return True
        return False
    
    @property
    def files(self) -> List[str]:
        """Liste aller Dateien im Manifest."""
        return list(set(t.file_name for t in self.tables))
    
    @property
    def total_tables(self) -> int:
        return len(self.tables)
    
    @property
    def total_cells(self) -> int:
        return sum(t.cell_count for t in self.tables)
    
    def export_csvs_to_folder(self, folder: Path) -> None:
        """Exportiert alle CSVs in einen Ordner."""
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        
        for table in self.tables:
            filename = f"{table.file_name.replace('.pdf', '')}_table_{table.table_id}.csv"
            (folder / filename).write_text(table.csv_data, encoding='utf-8')
    
    @classmethod
    def import_from_folder(cls, folder: Path, file_pattern: str = "*_table_*.csv") -> "CSVGroundTruthManifest":
        """
        Importiert CSVs aus einem Ordner.
        Erwartet Dateinamen wie: dokument_table_1.csv
        """
        manifest = cls()
        folder = Path(folder)
        
        for csv_file in folder.glob(file_pattern):
            # Parse Dateiname
            name = csv_file.stem
            parts = name.rsplit("_table_", 1)
            
            if len(parts) == 2:
                pdf_name = parts[0] + ".pdf"
                try:
                    table_id = int(parts[1])
                except ValueError:
                    continue
                
                gt = CSVGroundTruth.from_csv_file(csv_file, table_id, pdf_name)
                manifest.add(gt)
        
        return manifest
