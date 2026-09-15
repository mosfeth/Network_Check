@echo off
REM FrontEnd Start Script - usa venv isolado
cd /d "%~dp0"

REM Libera porta 8502 se estiver em uso
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8502') do (
    taskkill /F /PID %%a >nul 2>&1
)

call venv\Scripts\activate.bat
python -m streamlit run app.py --server.port 8502 --server.headless true