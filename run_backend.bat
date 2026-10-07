@echo off
echo Starting CodeMate AI Backend on http://127.0.0.1:8000 ...
cd /d "%~dp0backend"
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
