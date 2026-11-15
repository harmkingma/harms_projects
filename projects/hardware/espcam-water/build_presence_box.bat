@echo off
rem Build the presence sensor box: STL/STEP/FCStd are written next to presence_box.py.
rem Set FREECADCMD to override the FreeCAD command-line executable.
setlocal
if not defined FREECADCMD set "FREECADCMD=%LOCALAPPDATA%\Programs\FreeCAD 1.1\bin\freecadcmd.exe"
if not exist "%FREECADCMD%" (
    echo freecadcmd.exe not found at "%FREECADCMD%". Set FREECADCMD to its full path.
    exit /b 1
)
"%FREECADCMD%" "%~dp0presence_box.py"
exit /b %ERRORLEVEL%
