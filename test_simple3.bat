@echo off
echo Teste 1
if not exist venv (
    echo venv nao existe
) else (
    echo venv existe
)
echo Teste 2
call venv\Scripts\activate.bat
echo Teste 3 - ativado
pip install -e ".[dev]" >nul 2>&1
echo Teste 4 - pip ok
if not exist ".env" (
    echo .env nao existe
) else (
    echo .env existe
)
echo Teste 5
supadiag service status >nul 2>&1
echo Teste 6 - service check ok
pause