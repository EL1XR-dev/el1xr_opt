"""Allow running the EEM26 directory as a module.

Usage (from the repository root):
    python data/EEM26            # creates case folders
    python data/EEM26 --clean    # recreates case folders from scratch
    python data/EEM26 --help     # show all options
"""
from EEM26_create_cases_v2 import main

if __name__ == "__main__":
    raise SystemExit(main())
