@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
pushd "%~dp0"
if defined RAG_LAB_PYTHON (
  "%RAG_LAB_PYTHON%" -X utf8 "%~dp0assistant.py" %*
) else (
  py -3.12 -X utf8 "%~dp0assistant.py" %*
)
set "LAB_EXIT=%ERRORLEVEL%"
popd
if not defined RAG_LAB_NO_PAUSE pause
exit /b %LAB_EXIT%
