# conf.py — RTD-robust Sphinx config
import os
import sys
import types

# ---------------------------------------------------------------------------
# Path setup: make the src/ package importable
# Adjust the relative path if this conf.py is not at docs/ or docs/rst/
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

# ---------------------------------------------------------------------------
# Project metadata
project = "VY4E-OptModel"
author = "VY4E Team"
copyright = "2025, VY4E"
language = "en"

# ---------------------------------------------------------------------------
# Extensions (load optional ones only if available)
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

# Optional UX extensions — safe-guarded
try:
    import sphinx_copybutton  # noqa: F401
    extensions.append("sphinx_copybutton")
except Exception:
    pass

autosummary_generate = True
autodoc_typehints = "description"
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
master_doc = "index"  # root_doc also works on Sphinx>=5

# ---------------------------------------------------------------------------
# HTML / Theme
try:
    import sphinx_rtd_theme  # noqa: F401
    html_theme = "sphinx_rtd_theme"
except Exception:
    html_theme = "alabaster"  # fallback if theme not installed

html_static_path = ["_static"]
# Put a tight 88×88 transparent PNG here; RTD serves _static by default
html_logo = "_static/logo-rtd-compact.png"
html_favicon = "_static/favicon.png"  # optional

html_theme_options = {
    "logo_only": True,
    "collapse_navigation": True,
    "navigation_depth": 1,     # 1 felt too shallow to users
    "sticky_navigation": True, # <-- fixed typo
    "style_external_links": True,
}

# Optional: explicit sidebar layout (RTD theme default is fine)
html_sidebars = {
    "**": [
        "globaltoc.html",
        "searchbox.html",
        # "relations.html",
    ]
}

# ---------------------------------------------------------------------------
# Build robustness on RTD: mock heavy deps and legacy module names
autodoc_mock_imports = [
    "pyomo", "gurobipy", "numpy", "pandas", "scipy",
]

def _safe_mock(names):
    for name in names:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

# Legacy/transition names that autosummary might try to import
_safe_mock([
    "vy4e_optmodel.Modules",
    "Modules",
    "Modules.oM_ModelFormulation",
    "Modules.oM_InputData",
])

# Stub package modules while refactoring (remove when stable/importable)
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

# ---------------------------------------------------------------------------
# UX niceties (only active if sphinx_copybutton is present)
copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True

# Custom CSS (optional)
def setup(app):
    css = os.path.join(os.path.dirname(__file__), "_static", "custom.css")
    if os.path.exists(css):
        app.add_css_file("custom.css")