# conf.py — RTD-robust Sphinx config
import os
import sys
import types

# --- Import path: point to your src/ package (adjust depth if your conf.py lives elsewhere)
# If your conf.py is in docs/ or docs/rst/, go up one or two levels accordingly.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))   # src/ layout

# --- Project metadata
project = "VY4E-OptModel"
author = "VY4E Team"
copyright = "2025, VY4E"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",  # optional
]

autosummary_generate = True
autodoc_typehints = "description"     # nicer type hints
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

napoleon_google_docstring = True
napoleon_numpy_docstring = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", {}),
    "pyomo": ("https://pyomo.readthedocs.io/en/stable/", {}),
}

templates_path = ["_templates"]
exclude_patterns = []
source_suffix = {".rst": "restructuredtext"}
master_doc = "index"
language = "en"

# --- HTML theme
try:
    import sphinx_rtd_theme  # noqa: F401
    html_theme = "sphinx_rtd_theme"
except Exception:
    html_theme = "alabaster"  # fallback

html_static_path = ["_static"]
html_logo = "../img/VY4E-OptModel_logo_v4.png"  # optional
html_theme_options = {
    "logo_only": True,
    "collapse_navigation": True,
    "navigation_depth": 1,
    "stycky_navigation": True,
    "style_external_links": True,
}

# Optional: fine-tune sidebar blocks (RTD theme supports this)
html_sidebars = {
    "**": [
        "globaltoc.html",            # navigation tree
        "searchbox.html",
        # "relations.html",          # prev/next links (add if you like)
    ]
}

# -- Build robustness on RTD -------------------------------------------------
# Mock heavy/missing deps to avoid import errors during API doc generation.
autodoc_mock_imports = [
    "pyomo", "gurobipy", "numpy", "pandas", "scipy",
]

# Stub legacy names if autosummary tries to import them
def _safe_mock(modnames):
    for name in modnames:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

_safe_mock([
    "vy4e_optmodel.Modules",
    "Modules",
    "Modules.oM_ModelFormulation",
    "Modules.oM_InputData",
])

# Optionally stub package modules while refactoring (remove when stable)
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

# -- UX niceties -------------------------------------------------------------
copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True

# Add custom CSS (optional)
def setup(app):
    if os.path.exists(os.path.join(os.path.dirname(__file__), "_static", "custom.css")):
        app.add_css_file("custom.css")
