@echo off
title Dak Sahayak - Launcher
echo ======================================================
echo       Launching Dak Sahayak Frontend and Backend
echo ======================================================
echo.
echo Launching Backend in a separate CMD window...
start "Dak Sahayak Backend" cmd /k "call \"%~dp0start_backend.cmd\""

timeout /t 2 /nobreak >nul

echo Launching Frontend in a separate CMD window...
start "Dak Sahayak Frontend" cmd /k "call \"%~dp0start_frontend.cmd\""

echo.
echo Both servers have been launched in separate Command Prompt windows!
echo - Backend:  http://localhost:5000
echo - Frontend: http://localhost:3000
echo.
echo Opening Dak Sahayak in your browser...
timeout /t 3 /nobreak >nul
start http://localhost:3000
echo.
pause
