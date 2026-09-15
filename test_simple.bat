@echo off
echo Teste 1
if not exist venv (
    echo venv nao existe
) else (
    echo venv existe
)
echo Teste 2
pause