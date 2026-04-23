@echo off
REM Launcher script for the Tomviz Windows standalone bundle.

set "SCRIPT_DIR=%~dp0"
set "ENV_DIR=%SCRIPT_DIR%env"

set "PATH=%ENV_DIR%\Library\bin;%ENV_DIR%\Scripts;%ENV_DIR%;%PATH%"
set "CONDA_PREFIX=%ENV_DIR%"

REM Qt/ParaView plugin paths
set "QT_PLUGIN_PATH=%ENV_DIR%\Library\plugins"
set "PV_PLUGIN_PATH=%ENV_DIR%\Library\lib\paraview-6.1\plugins"

"%ENV_DIR%\Library\bin\tomviz.exe" %*
