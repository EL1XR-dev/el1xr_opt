# IZERO-OptModel

<img src="https://raw.githubusercontent.com/izero-nexus/.github/main/profile/IZERO_Nexus_avatar_tron_unified.png" width="120" align="right" />

**IZERO-OptModel** is the **core optimization engine** of the [IZERO Nexus](https://github.com/izero-nexus) ecosystem.  
It provides the fundamental modelling framework for **integrated zero-carbon energy systems**, supporting electricity, heat, hydrogen, and storage.

---

## 🚀 Features
- Modular formulation for multi-vector energy systems
- Compatible with **deterministic, stochastic, and equilibrium** approaches
- Flexible temporal structure: hours, days, representative periods
- Built on **[JuMP](https://jump.dev)/Pyomo** (depending on module choice)
- Interfaces with `izero-data` (datasets) and `izero-examples` (notebooks)

---

## 📂 Structure
- `src/`: Contains the core source code for the optimization model.
  - `oM_Main.py`: The main script to run the optimization model. It parses command-line arguments and calls the different modules in sequence.
  - `Modules/`: Contains the different modules of the optimization model.
    - `oM_InputData.py`: Reads and processes the input data from CSV files, and creates the model's variables.
    - `oM_ModelFormulation.py`: Defines the objective function and constraints of the optimization problem.
    - `oM_ProblemSolving.py`: Solves the optimization problem using the selected solver.
    - `oM_OutputData.py`: Saves the results of the optimization to CSV files.
- `data/`: Contains sample case studies.
  - `Home1/`: A sample case study with input data.
    - `oM_Dict_*.csv`: CSV files that define the sets for the model (e.g., nodes, generators, technologies).
    - `oM_Data_*.csv`: CSV files that contain the parameters for the model (e.g., demand, generation capacity, costs).
    - `Master_InputData_Home1.xlsm`: The Excel master file used to generate the CSV data files.
- `docs/`: Contains documentation and formulation notes.
  - `ppt/`: Contains a PowerPoint presentation with additional information about the model.
- `tests/`: Contains validation and regression tests.

---

## 📦 Installation
```bash
git clone https://github.com/izero-nexus/IZERO-OptModel.git
cd IZERO-OptModel
# Install dependencies (to be specified, e.g. Julia packages or Python venv)
```

---

## 🚀 Usage
To run the optimization model, use the `oM_Main.py` script from the `src` directory.

```bash
python src/oM_Main.py --case <case_name> --solver <solver_name>
```

### Command-line Arguments
- `--dir`: The directory containing the case data. Defaults to the current directory.
- `--case`: The name of the case to run (e.g., `Home1`).
- `--solver`: The name of the solver to use (e.g., `gurobi`, `cbc`, `cplex`).
- `--date`: The date for the model run, in "YYYY-MM-DD HH:MM:SS" format. Defaults to the current date and time.
- `--rawresults`: Whether to save raw results. Can be `True` or `False`. Defaults to `False`.
- `--plots`: Whether to generate plots. Can be `True` or `False`. Defaults to `False`.

---

## 🧩 Dependencies
The model is developed in Python 3.12 and requires the following main libraries:
- **Pyomo**: For the optimization modeling.
- **Pandas**: For data manipulation.
- **Altair, Plotly**: For data visualization.
- **Gurobipy**: As an interface to the Gurobi solver.
- **Colour**: For color representation.
- **Psutil**: For cross-platform lib for process and system monitoring in Python.
