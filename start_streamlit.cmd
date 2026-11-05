@echo off
rem ============================================================
rem  One-click launcher for the Streamlit version of the RAG lab.
rem  ASCII-only on purpose: cmd reads .cmd files as GBK.
rem  - starts the local mock model server if it is not running
rem  - trusts the local self-signed certificate, bypasses proxy
rem  - serves the Streamlit app on http://127.0.0.1:8501
rem  Keep this window open while working on the lab.
rem ============================================================
set WORK=D:\workbuddy\2026-10-27-08-47-18
set SSL_CERT_FILE=%WORK%\certs\cert.pem
set NO_PROXY=localhost,127.0.0.1
set no_proxy=localhost,127.0.0.1
if not exist "%WORK%\logs" mkdir "%WORK%\logs"
cd /d "%~dp0"

curl -s -o nul -m 3 -k https://localhost:8443/v1/chat/completions 2>nul
if not errorlevel 1 goto :model_ok
echo Starting local model server...
start "RAG mock model server" /min cmd /c "python -u -X utf8 "%WORK%\mock_model_server.py" >> "%WORK%\logs\model_server.log" 2>&1"
ping -n 6 127.0.0.1 >nul
curl -s -o nul -m 4 -k https://localhost:8443/v1/chat/completions 2>nul
if errorlevel 1 goto :model_fail

:model_ok
echo [OK] model server ready on https://localhost:8443
echo [OK] Streamlit app: http://127.0.0.1:8501
python -m streamlit run streamlit_app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
goto :done

:model_fail
echo [ERROR] model server did not start. Log:
type "%WORK%\logs\model_server.log"
pause
exit /b 1

:done
pause
