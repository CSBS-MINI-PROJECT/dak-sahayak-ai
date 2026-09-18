@echo off
title Dak Sahayak - Backend (Port 5000)
cd /d "%~dp0dak-backend"

echo ======================================================
echo           Starting Dak Sahayak Backend (Flask)
echo ======================================================
echo Directory: %CD%
echo.

if exist "%~dp0dak-backend\venv\Scripts\activate.bat" (
    echo Activating venv in dak-backend...
    call "%~dp0dak-backend\venv\Scripts\activate.bat"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    echo Activating root venv...
    call "%~dp0venv\Scripts\activate.bat"
) else (
    echo [WARNING] No venv found, using system Python...
)

echo.
echo Starting Flask server on http://localhost:5000 ...
python app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Backend exited with error code %ERRORLEVEL%.
)
pause
