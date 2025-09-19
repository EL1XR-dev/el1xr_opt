# conf.py — RTD-robust Sphinx config
import os
import sys
import types

# --- Import path: point to your src/ package (adjust depth if your conf.py lives elsewhere)
# If your conf.py is in docs/ or docs/rst/, go up one or two levels accordingly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

# --- Project metadata
project = "VY4E-OptModel"
author = "VY4E"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_design",  # optional, for fancier admonitions
    "sphinx_copybutton",  # optional, for copy buttons on code blocks
]
copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True

autosummary_generate = True
napoleon_google_docstring = True
napoleon_numpy_docstring = True

# --- HTML theme
try:
    import sphinx_rtd_theme  # noqa: F401
    html_theme = "sphinx_rtd_theme"
except Exception:
    html_theme = "alabaster"  # fallback

html_logo = "_static/logo-rtd-compact.png"  # optional
html_static_path = ["_static"]
html_theme_options = {
    "logo_only": True,
    "collapse_navigation": True,
    "navigation_depth": 1,
}

# --- Make imports safe on RTD
autodoc_mock_imports = [
    "pyomo", "gurobipy", "numpy", "pandas", "scipy",
    # add any other heavy deps here
]

def _safe_mock(modnames):
    for name in modnames:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

# Legacy/internal names that autosummary tries to import; stub them
_safe_mock([
    "vy4e_optmodel.Modules",
    "Modules",
    "Modules.oM_ModelFormulation",
    "Modules.oM_InputData",
])

# If the real package is not importable yet (e.g., mid-refactor),
# stub the new src/ package modules so autosummary won’t crash.
try:
    import vy4e_optmodel  # noqa: F401
except Exception:
    _safe_mock([
        "vy4e_optmodel",
        "vy4e_optmodel.data",
        "vy4e_optmodel.model",
        "vy4e_optmodel.optimization",
        "vy4e_optmodel.scenarios",
        "vy4e_optmodel.solvers",
        "vy4e_optmodel.results",
        "vy4e_optmodel.cli",
    ])

# --- General Sphinx knobs
templates_path = ["_templates"]
exclude_patterns = []
source_suffix = {".rst": "restructuredtext"}
master_doc = "index"  # or "contents" if you renamed it
