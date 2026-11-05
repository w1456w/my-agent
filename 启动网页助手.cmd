@echo off
rem ============================================================
rem  RAG Web Assistant - one click launcher
rem  1) make sure local mock model server (port 8443) is running
rem  2) start web server on http://127.0.0.1:8765
rem  Keep this window open while using the web app.
rem ============================================================
cd /d %~dp0
curl -s -o nul -m 2 -k https://localhost:8443/ 2>nul
if errorlevel 1 (
    echo Starting local model server...
    start "mock-model" /min python -X utf8 D:\workbuddy\2026-10-27-08-47-18\mock_model_server.py
    timeout /t 3 /nobreak >nul
)
echo Web app: http://127.0.0.1:8765
python -X utf8 web_server.py
pause
