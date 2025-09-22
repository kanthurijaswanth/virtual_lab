@echo off
setlocal ENABLEDELAYEDEXPANSION

rem === MMT Virtual Lab — Qt Launcher build (matching your filenames) ===

set "PROJ=%~dp0"
cd /d "%PROJ%"
echo.
echo === MMT Virtual Lab: Qt launcher build ===
echo Project: %CD%
echo.

rem LOOK FOR YOUR FILE (virtual_lab_launcher.py)
if not exist "launcher\virtual_lab_launcher.py" (
  echo [ERROR] launcher\virtual_lab_launcher.py not found.
  echo         Make sure the file exists in "mmt-virtual-lab\launcher\".
  exit /b 1
)

set "PY="
where py >NUL 2>NUL && set "PY=py -3"
if "%PY%"=="" ( where python >NUL 2>NUL && set "PY=python" )
if "%PY%"=="" (
  echo [ERROR] Python not found. Install 64-bit Python 3.10–3.12 and re-run.
  exit /b 1
)

for /f "delims=" %%v in ('%PY% -c "import platform,sys;print(platform.architecture()[0], sys.version.split()[0])"') do set "PYINFO=%%v"
echo Using: %PY%   (%PYINFO%)
echo.

if not exist ".venv\" (
  echo Creating venv .venv...
  %PY% -m venv .venv || (echo [ERROR] venv create failed & exit /b 1)
) else (
  echo Using existing .venv
)

set "VENV_PY=.venv\Scripts\python.exe"
echo Upgrading pip/setuptools/wheel...
"%VENV_PY%" -m pip install --upgrade pip setuptools wheel || (echo [ERROR] pip upgrade failed & exit /b 1)

echo Installing PySide6 + PyInstaller...
"%VENV_PY%" -m pip install PySide6 pyinstaller || (echo [ERROR] deps install failed & exit /b 1)

if exist build rd /s /q build
if exist dist rd /s /q dist
if exist virtual_lab_launcher.spec del /q virtual_lab_launcher.spec

echo Building EXE (name: virtual_lab_launcher.exe)...
".venv\Scripts\pyinstaller.exe" --onefile --noconsole ^
  --name virtual_lab_launcher ^
  launcher\virtual_lab_launcher.py || (echo [ERROR] build failed & exit /b 1)

if not exist "dist\virtual_lab_launcher.exe" (
  echo [ERROR] Expected dist\virtual_lab_launcher.exe not found.
  exit /b 1
)

echo.
echo Build SUCCESS: %CD%\dist\virtual_lab_launcher.exe
pause
exit /b 0
