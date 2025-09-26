"""
el1xr_opt: An open-source optimization model for the design and operation of hybrid renewable energy systems.


    Args:
        case:   Name of the folder where the CSV files of the case are found
        dir:    Main path where the case folder can be found
        solver: Name of the solver

    Returns:
        Output results in CSV files that are found in the case folder.

    Examples:
        >>> import el1xr_opt as eo
        >>> eo.routine("Home1", "C:\\Users\\UserName\\Documents\\GitHub\\el1xr_opt", "glpk")
"""
# __version__ = "1.0.16rc1"

from . import oM_InputData
from . import oM_ModelFormulation
from . import oM_OutputData
from . import oM_ProblemSolving
