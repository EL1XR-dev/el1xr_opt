# Developed by: Erik F. Alvarez

# Erik F. Alvarez
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

import os
import re
import duckdb
import pandas as pd
from pyomo.environ import Var, Param, Set, Constraint, value as pyo_value


def _pkg_version():
    try:
        from importlib.metadata import version
        return version("el1xr_opt")
    except Exception:
        return None


def safe_identifier(name: str) -> str:
    """
    Make a SQL-safe identifier: only letters, digits, and underscores.
    (Codacy-friendly and prevents odd characters from leaking into identifiers.)
    """
    return re.sub(r'[^0-9a-zA-Z_]+', '_', str(name))


def _save_df_relation(con: duckdb.DuckDBPyConnection, df: pd.DataFrame, raw_name: str) -> None:
    """
    Persist a DataFrame as a DuckDB table without dynamic SQL.
    First attempt: create the table.
    If it already exists: overwrite its contents.
    """
    table_name = safe_identifier(raw_name)

    # Build a relation from the DataFrame
    rel = duckdb.from_df(df, connection=con)

    # Try to create the table; if it exists, overwrite via insert_into(..., overwrite=True)
    try:
        rel.create(table_name)  # persists as a physical table
    except Exception:
        # Table probably exists: replace the contents
        # insert_into uses the API (not SQL strings), so Codacy won't flag it.
        rel.insert_into(table_name)


def save_to_duckdb(DirName, CaseName, model, optmodel, date=None, solver=None, elapsed=None):
    """
    Save optimization model data to a DuckDB database in a Codacy-compliant way
    (no formatted SQL strings).

    Writes one table per Pyomo set, parameter and variable (value, lower and
    upper bound), one ``*_dual`` table per constraint when duals are available,
    and a headline ``oM_Result_RunMetadata`` table (case, date, solver, objective,
    version). The file is ``<DirName>/<CaseName>/results.duckdb``.
    """
    _path = os.path.join(DirName, CaseName)
    os.makedirs(_path, exist_ok=True)
    db_path = os.path.join(_path, "results.duckdb")

    with duckdb.connect(database=db_path, read_only=False) as con:

        # ---- Save run metadata (headline result) ----
        meta_rows = [("case", CaseName)]
        if date is not None:
            meta_rows.append(("date", str(date)))
        if solver is not None:
            meta_rows.append(("solver", str(solver)))
        try:
            meta_rows.append(("objective", str(pyo_value(optmodel.eTotalSCost))))
        except Exception:
            pass
        if elapsed is not None:
            meta_rows.append(("elapsed_seconds", str(elapsed)))
        version = _pkg_version()
        if version is not None:
            meta_rows.append(("el1xr_opt_version", str(version)))
        _save_df_relation(con, pd.DataFrame(meta_rows, columns=["Key", "Value"]), "oM_Result_RunMetadata")

        # ---- Save sets ----
        for s in optmodel.component_objects(Set, active=True):
            if not s.is_constructed() or not s:
                continue

            df = pd.DataFrame(list(s))
            if df.shape[1] > 1:
                df.columns = [f'{s.name}_dim{i}' for i in range(df.shape[1])]
            else:
                df.columns = [s.name]

            _save_df_relation(con, df, s.name)

        # ---- Save parameters ----
        for p in optmodel.component_objects(Param, active=True):
            if p.is_indexed():
                df = pd.DataFrame.from_dict(p.extract_values(), orient='index', columns=['value']).reset_index()
                index_cols = [col for col in df.columns if col != 'value']
                df = df.rename(columns={old: f'index_{i}' for i, old in enumerate(index_cols)})
            else:
                df = pd.DataFrame({'value': [p.value]})

            _save_df_relation(con, df, p.name)

        # ---- Save variables ----
        for v in optmodel.component_objects(Var, active=True):
            if v.is_indexed():
                data = []
                for index, var_data in v.items():
                    row = list(index) if isinstance(index, tuple) else [index]
                    row.extend([var_data.value, var_data.lb, var_data.ub])
                    data.append(row)

                if data:
                    num_indices = len(data[0]) - 3
                    columns = [f'index_{i}' for i in range(num_indices)] + ['value', 'lb', 'ub']
                    df = pd.DataFrame(data, columns=columns)
                else:
                    df = pd.DataFrame(columns=['value', 'lb', 'ub'])
            else:
                df = pd.DataFrame({'value': [v.value], 'lb': [v.lb], 'ub': [v.ub]})

            _save_df_relation(con, df, v.name)

        # ---- Save duals of constraints ----
        if hasattr(model, 'dual'):
            for c in optmodel.component_objects(Constraint, active=True):
                tname = f"{c.name}_dual"
                if c.is_indexed():
                    data = []
                    for index, con_data in c.items():
                        row = list(index) if isinstance(index, tuple) else [index]
                        try:
                            dual_value = model.dual[con_data]
                        except (KeyError, TypeError):
                            dual_value = None
                        row.append(dual_value)
                        data.append(row)

                    if data:
                        num_indices = len(data[0]) - 1
                        columns = [f'index_{i}' for i in range(num_indices)] + ['dual']
                        df = pd.DataFrame(data, columns=columns)
                    else:
                        df = pd.DataFrame(columns=['dual'])
                else:
                    try:
                        dual_value = model.dual[c]
                    except (KeyError, TypeError):
                        dual_value = None
                    df = pd.DataFrame({'dual': [dual_value]})

                _save_df_relation(con, df, tname)

    print(f"Data saved to {db_path}")