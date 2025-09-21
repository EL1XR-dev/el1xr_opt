"""
VY4E-OptModel: An open-source optimization model for the design and operation of hybrid renewable energy systems.


    Args:
        case:   Name of the folder where the CSV files of the case are found
        dir:    Main path where the case folder can be found
        solver: Name of the solver

    Returns:
        Output results in CSV files that are found in the case folder.

    Examples:
        >>> import VY4E-OptModel as oM
        >>> oM.routine("VPP1", "C:\\Users\\UserName\\Documents\\GitHub\\VY4E-OptModel", "glpk")
"""
__version__ = "1.0.15rc6"

from .oM_Main import main
