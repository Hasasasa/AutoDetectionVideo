@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo.
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Failed to install dependencies.
  pause
  exit /b 1
)

echo Running detection...
".venv\Scripts\python.exe" app.py --config config.json

if errorlevel 1 (
  echo.
  echo Failed. Check config.json and your input folder.
) else (
  echo.
  echo Finished.
)

pause
