@echo off
echo Starting CaseDesk...

:: Start Backend (Using the virtual environment)
cd /d "e:\updated_casedesk\backend"
start "CaseDesk Backend" cmd /c "call ..\venv\Scripts\activate.bat && uvicorn main:app --host 0.0.0.0 --port 8000"

:: Start Frontend
cd /d "e:\updated_casedesk\frontend"
start "CaseDesk Frontend" cmd /c "python -m http.server 5500"

:: Wait 3 seconds for servers to start, then open the browser
timeout /t 3 /nobreak > nul
start http://127.0.0.1:5500
