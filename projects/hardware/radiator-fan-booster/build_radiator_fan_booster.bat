@echo off
rem Build the radiator fan booster parts: print\*.stl, STEP and FCStd are written next to the .py.
rem Set FREECADCMD to override the FreeCAD command-line executable.
setlocal
if not defined FREECADCMD set "FREECADCMD=%LOCALAPPDATA%\Programs\FreeCAD 1.1\bin\freecadcmd.exe"
if not exist "%FREECADCMD%" (
    echo freecadcmd.exe not found at "%FREECADCMD%". Set FREECADCMD to its full path.
    exit /b 1
)
"%FREECADCMD%" "%~dp0radiator_fan_booster.py"
exit /b %ERRORLEVEL%
