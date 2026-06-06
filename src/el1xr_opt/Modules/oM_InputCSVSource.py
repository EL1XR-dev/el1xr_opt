"""el1xr_opt CSV backend — reads a directory of ``oM_Dict_*`` / ``oM_Data_*`` files.

This preserves the model's historical reading behaviour exactly: each data
table is read with ``pd.read_csv`` and its leading unnamed columns are set as a
nameless index.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .oM_InputSchema import DATA_PREFIX, DICT_PREFIX
from .oM_InputSource import InputSource, finalize_data_index


class CSVSource(InputSource):
    def __init__(self, case_dir) -> None:
        self.case_dir = Path(case_dir)
        cn = self._detect_case_name(self.case_dir)
        if cn is None:
            raise ValueError(
                f"{self.case_dir}: cannot detect case name (no oM_Data_Parameter_*.csv found)"
            )
        self.case_name = cn

    @property
    def dir_name(self) -> str:
        return str(self.case_dir.parent)

    @staticmethod
    def _detect_case_name(case_dir: Path):
        for p in case_dir.glob(f"{DATA_PREFIX}Parameter_*.csv"):
            return p.stem[len(f"{DATA_PREFIX}Parameter_"):]
        return None

    def list_data_stems(self) -> set:
        stems: set = set()
        suffix = f"_{self.case_name}.csv"
        for p in self.case_dir.glob(f"{DATA_PREFIX}*.csv"):
            name = p.name
            if name.endswith(suffix):
                inner = name[len(DATA_PREFIX):-len(suffix)]
                if inner:
                    stems.add(inner)
        return stems

    def list_dict_stems(self) -> set:
        stems: set = set()
        suffix = f"_{self.case_name}.csv"
        for p in self.case_dir.glob(f"{DICT_PREFIX}*.csv"):
            name = p.name
            if name.endswith(suffix):
                inner = name[len(DICT_PREFIX):-len(suffix)]
                if inner:
                    stems.add(inner)
        return stems

    def read_dict(self, stem: str) -> pd.DataFrame:
        path = self.case_dir / f"{DICT_PREFIX}{stem}_{self.case_name}.csv"
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)

    def read_data(self, stem: str) -> pd.DataFrame:
        path = self.case_dir / f"{DATA_PREFIX}{stem}_{self.case_name}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        df = pd.read_csv(path)
        unnamed_cols = [c for c in df.columns if "Unnamed" in str(c)]
        return finalize_data_index(df, unnamed_cols)
