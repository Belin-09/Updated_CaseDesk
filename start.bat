@echo off
title CaseDesk Launcher
echo ==================================================
echo              Starting CaseDesk...
echo ==================================================

set WORKSPACE_DIR=%~dp0

echo Starting Backend API (port 8000)...
start "CaseDesk Backend" cmd /k "cd /d %WORKSPACE_DIR%backend && %WORKSPACE_DIR%venv\Scripts\activate && uvicorn main:app --reload --port 8000"

echo Starting Frontend Server (port 5500)...
start "CaseDesk Frontend" cmd /k "cd /d %WORKSPACE_DIR%frontend && %WORKSPACE_DIR%venv\Scripts\activate && python -m http.server 5500"

timeout /t 3 >nul
echo Opening CaseDesk in your default browser...
start http://127.0.0.1:5500

echo ==================================================
echo CaseDesk is now running!
echo ==================================================
