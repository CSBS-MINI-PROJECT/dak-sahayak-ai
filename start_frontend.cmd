@echo off
title Dak Sahayak - Frontend (Port 3000)
cd /d "%~dp0dak-frontend"

echo ======================================================
echo           Starting Dak Sahayak Frontend (Next.js)
echo ======================================================
echo Directory: %CD%
echo.

if not exist "node_modules\" (
    echo Installing node dependencies...
    call npm install
)

echo Starting Next.js development server on http://localhost:3000 ...
call npm run dev

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Frontend exited with error code %ERRORLEVEL%.
)
pause
