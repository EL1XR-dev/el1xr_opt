Quickstart
==========

Run a minimal case
------------------
Python::

    from el1xr_opt.Modules.oM_Sequence import routine
    from el1xr_opt.Modules.oM_LoadCase import load_case

    data = load_case("Home1")

    m = routine(**data)

CLI (if enabled)::

    python -m el1xr_opt --dir <folder_parent_case> --case <case_folder_name> --solver  <solver_name> --date <date_string> --rawresults <'Yes'-or-'No'> --plots <'Yes'-or-'No'>
