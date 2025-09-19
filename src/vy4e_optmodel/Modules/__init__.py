"""
Open Generation, Storage, and Transmission Operation and Expansion Planning Model with RES and ESS (openTEPES)


    Args:
        case:   Name of the folder where the CSV files of the case are found
        dir:    Main path where the case folder can be found
        solver: Name of the solver

    Returns:
        Output results in CSV files that are found in the case folder.

    Examples:
        >>> import vy4e_optmodel as oM
        >>> oM.routine("9n", "C:\\Users\\UserName\\Documents\\GitHub\\vy4e_optmodel", "glpk")
"""
__version__ = "1.0.1"

from .oM_InputData        import *
from .oM_ModelFormulation import *
from .oM_ProblemSolving   import *
from .oM_OutputResults    import *
