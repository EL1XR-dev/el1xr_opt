# Developed by: Erik F. Alvarez

# Erik F. Alvarez
# Electric Power System Unit
# RISE
# erik.alvarez@ri.se

# Importing Libraries
import os
import duckdb
import pandas as pd
from pyomo.environ import Var, Param, Set, Constraint

def save_to_duckdb(DirName, CaseName, model, optmodel):
    """
    Save optimization model data to a DuckDB database.

    This function iterates through all active sets, parameters, and variables
    in the optimization model and saves their data to separate tables in a DuckDB database.

    Args:
        DirName (str): The directory where the result files will be saved.
        CaseName (str): The name of the case, used for the database file name.
        model: The optimization model object, used for accessing duals.
        optmodel: The concrete optimization model instance.
    """
    _path = os.path.join(DirName, CaseName)
    db_path = os.path.join(_path, "results.duckdb")
    con = duckdb.connect(database=db_path, read_only=False)

    # Save sets
    for s in optmodel.component_objects(Set, active=True):
        if not s.is_constructed() or not s:
            continue

        df = pd.DataFrame(list(s))
        if df.shape[1] > 1:
            df.columns = [f'{s.name}_dim{i}' for i in range(df.shape[1])]
        else:
            df.columns = [s.name]

        con.register('tmp_view', df)
        con.execute(f'CREATE OR REPLACE TABLE "{s.name}" AS SELECT * FROM tmp_view')
        con.unregister('tmp_view')

    # Save parameters
    for p in optmodel.component_objects(Param, active=True):
        if p.is_indexed():
            df = pd.DataFrame.from_dict(p.extract_values(), orient='index', columns=['value'])
            df = df.reset_index()
            index_cols = [col for col in df.columns if col != 'value']
            rename_dict = {old_name: f'index_{i}' for i, old_name in enumerate(index_cols)}
            df = df.rename(columns=rename_dict)
        else:
            df = pd.DataFrame({'value': [p.value]})

        con.register('tmp_view', df)
        con.execute(f'CREATE OR REPLACE TABLE "{p.name}" AS SELECT * FROM tmp_view')
        con.unregister('tmp_view')

    # Save variables
    for v in optmodel.component_objects(Var, active=True):
        if v.is_indexed():
            data = []
            for index, var_data in v.items():
                row = list(index) if isinstance(index, tuple) else [index]
                row.extend([var_data.value, var_data.lb, var_data.ub])
                data.append(row)

            if data:
                num_indices = len(data[0]) - 3
                columns = [f'index_{i}' for i in range(num_indices)]
                columns.extend(['value', 'lb', 'ub'])
                df = pd.DataFrame(data, columns=columns)
            else:
                df = pd.DataFrame(columns=['value', 'lb', 'ub'])
        else:
            df = pd.DataFrame({'value': [v.value], 'lb': [v.lb], 'ub': [v.ub]})

        con.register('tmp_view', df)
        con.execute(f'CREATE OR REPLACE TABLE "{v.name}" AS SELECT * FROM tmp_view')
        con.unregister('tmp_view')

    # Save duals of constraints
    for c in optmodel.component_objects(Constraint, active=True):
        if not hasattr(model, 'dual'):
            continue

        table_name = f"{c.name}_dual"
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
                columns = [f'index_{i}' for i in range(num_indices)]
                columns.append('dual')
                df = pd.DataFrame(data, columns=columns)
            else:
                df = pd.DataFrame(columns=['dual'])
        else:
            try:
                dual_value = model.dual[c]
            except (KeyError, TypeError):
                dual_value = None
            df = pd.DataFrame({'dual': [dual_value]})

        con.register('tmp_view', df)
        con.execute(f'CREATE OR REPLACE TABLE "{table_name}" AS SELECT * FROM tmp_view')
        con.unregister('tmp_view')

    con.close()
    print(f"Data saved to {db_path}")