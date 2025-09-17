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
- `src/` — core model formulation  
- `data/` — sample case studies (linked to [izero-data](https://github.com/izero-nexus/izero-data))  
- `docs/` — documentation and formulation notes  
- `tests/` — validation and regression tests  

---

## 📦 Installation
```bash
git clone https://github.com/izero-nexus/IZERO-OptModel.git
cd IZERO-OptModel
# Install dependencies (to be specified, e.g. Julia packages or Python venv)
