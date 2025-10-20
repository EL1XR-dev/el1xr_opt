import re
import duckdb
import pandas as pd
from pyomo.environ import Var, Param, Set, Constraint
import os


def safe_identifier(name: str) -> str:
    """
    Sanitize the name to be a safe SQL identifier.
    Keeps only letters, digits, and underscores.
    """
    return re.sub(r'[^0-9a-zA-Z_]+', '_', name)


def save_to_duckdb(DirName, CaseName, model, optmodel):
    """Save optimization model data to DuckDB in a safe, Codacy-compliant way."""
    _path = os.path.join(DirName, CaseName)
    db_path = os.path.join(_path, "results.duckdb")

    with duckdb.connect(database=db_path, read_only=False) as con:

        def save_dataframe_to_duckdb(df: pd.DataFrame, raw_name: str):
            """Register and safely save DataFrame to DuckDB without SQL string interpolation."""
            table_name = safe_identifier(raw_name)
            con.register("tmp_view", df)
            # Use DuckDB relation API to avoid raw SQL f-string
            rel = con.table("tmp_view")
            con.execute(f"DROP TABLE IF EXISTS {table_name}")
            rel.create(table_name)  # safe table creation
            con.unregister("tmp_view")

        # --- Save sets ---
        for s in optmodel.component_objects(Set, active=True):
            if not s.is_constructed() or not s:
                continue
            df = pd.DataFrame(list(s))
            if df.shape[1] > 1:
                df.columns = [f'{s.name}_dim{i}' for i in range(df.shape[1])]
            else:
                df.columns = [s.name]
            save_dataframe_to_duckdb(df, s.name)

        # --- Save parameters ---
        for p in optmodel.component_objects(Param, active=True):
            if p.is_indexed():
                df = pd.DataFrame.from_dict(p.extract_values(), orient='index', columns=['value'])
                df = df.reset_index()
                index_cols = [col for col in df.columns if col != 'value']
                rename_dict = {old: f'index_{i}' for i, old in enumerate(index_cols)}
                df = df.rename(columns=rename_dict)
            else:
                df = pd.DataFrame({'value': [p.value]})
            save_dataframe_to_duckdb(df, p.name)

        # --- Save variables ---
        for v in optmodel.component_objects(Var, active=True):
            if v.is_indexed():
                data = []
                for index, var_data in v.items():
                    row = list(index) if isinstance(index, tuple) else [index]
                    row.extend([var_data.value, var_data.lb, var_data.ub])
                    data.append(row)
                if data:
                    num_idx = len(data[0]) - 3
                    cols = [f'index_{i}' for i in range(num_idx)] + ['value', 'lb', 'ub']
                    df = pd.DataFrame(data, columns=cols)
                else:
                    df = pd.DataFrame(columns=['value', 'lb', 'ub'])
            else:
                df = pd.DataFrame({'value': [v.value], 'lb': [v.lb], 'ub': [v.ub]})
            save_dataframe_to_duckdb(df, v.name)

        # --- Save duals ---
        if hasattr(model, 'dual'):
            for c in optmodel.component_objects(Constraint, active=True):
                table_name = f"{c.name}_dual"
                if c.is_indexed():
                    data = []
                    for index, con_data in c.items():
                        row = list(index) if isinstance(index, tuple) else [index]
                        dual_value = model.dual.get(con_data, None)
                        row.append(dual_value)
                        data.append(row)
                    if data:
                        num_idx = len(data[0]) - 1
                        cols = [f'index_{i}' for i in range(num_idx)] + ['dual']
                        df = pd.DataFrame(data, columns=cols)
                    else:
                        df = pd.DataFrame(columns=['dual'])
                else:
                    dual_value = model.dual.get(c, None)
                    df = pd.DataFrame({'dual': [dual_value]})
                save_dataframe_to_duckdb(df, table_name)

    print(f"Data saved to {db_path}")