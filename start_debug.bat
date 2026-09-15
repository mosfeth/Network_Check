@echo on
echo Iniciando start.bat
if not exist venv (
    echo [1] Criando venv...
    python -m venv venv
    if errorlevel 1 (
        echo ERRO venv
        pause
        exit /b 1
    )
) else (
    echo [1] venv existe
)
echo Passou bloco 1

call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERRO activate
    pause
    exit /b 1
)
echo Passou bloco 2

pip install -e ".[dev]" >nul 2>&1
if errorlevel 1 (
    echo ERRO pip
    pause
    exit /b 1
)
echo Passou bloco 3

if not exist ".env" (
    echo .env nao existe
    copy .env.example .env >nul
    pause
)
echo Passou bloco 4

supadiag service status >nul 2>&1
if errorlevel 1 (
    echo Servico nao instalado, instalando...
    supadiag service install
    if errorlevel 1 (
        echo ERRO servico
        pause
        exit /b 1
    )
) else (
    echo Servico ja instalado
)
echo Passou bloco 5

supadiag check
if errorlevel 1 (
    echo AVISO: check falhou
)
echo Passou bloco 6

start "SupaDiag Monitor" cmd /c "supadiag monitor"
echo Monitor iniciado
pause