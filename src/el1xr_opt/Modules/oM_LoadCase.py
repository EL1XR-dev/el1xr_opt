# Script for creating load cases in oM
import os
import datetime
from typing import Optional, Dict, Union

def load_case(
    directory: Optional[str] = None,
    case: Optional[str] = None,
    date: Optional[Union[str, datetime.datetime]] = None,
    solver: str = "highs",
    rawresults: bool = False,
    plots: bool = False,
) -> Dict[str, Union[str, datetime.datetime, bool]]:
    """
    Create and validate a load case configuration.

    Args:
        dir (str, optional): Directory where the case is located.
                             Defaults to "../site-packages/el1xr_opt".
        case (str, optional): Name of the case to load. Defaults to "Grid1".
        date (datetime or str, optional): Date information.
                                          If string, it should follow "%Y-%m-%d %H:%M".
                                          Defaults to current datetime (rounded to minute).
        solver (str, optional): Solver to be used. Defaults to "highs".
        rawresults (bool, optional): Whether to save raw results. Defaults to False.
        plots (bool, optional): Whether to generate plots. Defaults to False.

    Returns:
        dict: A dictionary containing the case configuration.
    """

    # Set defaults
    dir_name = directory or os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../")
    )
    print("Dir: ",dir_name)
    case_name = case or "Grid1"

    # Handle date input
    if date is None:
        date_info = datetime.datetime.now().replace(second=0, microsecond=0)
    elif isinstance(date, str):
        try:
            date_info = datetime.datetime.strptime(date, "%Y-%m-%d %H:%M")
        except ValueError:
            raise ValueError("Date string must follow format '%Y-%m-%d %H:%M'")
    elif isinstance(date, datetime.datetime):
        date_info = date
    else:
        raise TypeError("date must be None, str, or datetime.datetime")

    # Validate case path
    case_path = os.path.join(dir_name, case_name)
    if not os.path.exists(case_path):
        raise FileNotFoundError(f"The specified case directory does not exist: {case_path}")

    # Build configuration dictionary
    case_data = {
        "dir": dir_name,
        "case": case_name,
        "solver": solver,
        "date": date_info,
        "rawresults": rawresults,
        "plots": plots,
    }

    return case_data
