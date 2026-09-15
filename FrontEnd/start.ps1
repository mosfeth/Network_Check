# FrontEnd Start Script - usa venv isolado
Set-Location $PSScriptRoot
& ".\venv\Scripts\Activate.ps1"
python -m streamlit run app.py --server.port 8502 --server.headless true