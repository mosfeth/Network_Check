# start.ps1 - Inicia o SupaDiag (monitor + servico agendado)
# Verifica venv, dependencias, servico no Agendador de Tarefas e inicia o monitor + dashboard Streamlit

Set-Location $PSScriptRoot

Write-Host "=========================================="
Write-Host "  SupaDiag - Inicializacao"
Write-Host "=========================================="
Write-Host ""

# 1. Verifica/cria ambiente virtual
if (-not (Test-Path "venv")) {
    Write-Host "[1/6] Criando ambiente virtual (venv)..."
    python -m venv venv
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ERRO: Falha ao criar venv. Verifique se Python 3.10+ esta no PATH."
        Read-Host "Pressione Enter para sair"
        exit 1
    }
} else {
    Write-Host "[1/6] Ambiente virtual ja existe."
}

# 2. Ativa venv
Write-Host "[2/6] Ativando ambiente virtual..."
. venv\Scripts\Activate.ps1
Write-Host "Ambiente virtual ativado."

# 2.5. Mata processos supadiag.exe se estiverem rodando (evita erro WinError 32 ao reinstalar)
Write-Host "[2.5/6] Verificando processos supadiag.exe em execucao..."
$supadiagProcesses = Get-Process -Name "supadiag" -ErrorAction SilentlyContinue
if ($supadiagProcesses) {
    Write-Host "Encontrado(s) $($supadiagProcesses.Count) processo(s) supadiag.exe. Finalizando..."
    $supadiagProcesses | Stop-Process -Force
    Start-Sleep -Seconds 1
}

# Refresca PATH apos ativacao do venv
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + $env:Path
$env:Path = $PSScriptRoot + "\venv\Scripts;" + $env:Path

# 3. Instala/atualiza dependencias
Write-Host "[3/6] Verificando/Instalando dependencias..."
pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    Write-Error "ERRO: Falha ao instalar dependencias. Verifique se o pyproject.toml existe e ha conexao de rede."
    Read-Host "Pressione Enter para sair"
    exit 1
} else {
    Write-Host "Dependencias OK."
}
# Refresca PATH apos instalacao (Windows precisa disso para reconhecer novos comandos)
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + $env:Path
if (Test-Path "venv\Scripts") { $env:Path = $PSScriptRoot + "\venv\Scripts;" + $env:Path }

# 4. Verifica arquivo .env
Write-Host "[4/6] Verificando configuracao (.env)..."
if (-not (Test-Path ".env")) {
    Write-Warning "AVISO: Arquivo .env nao encontrado. Copiando de .env.example..."
    Copy-Item .env.example .env
    Write-Host "EDITE o arquivo .env com suas credenciais do Supabase antes de continuar."
    Read-Host "Pressione Enter para continuar"
}

# 5. Verifica/instala servico no Agendador de Tarefas
Write-Host "[5/6] Verificando servico no Agendador de Tarefas..."
$supadiagCmd = if (Get-Command supadiag -ErrorAction SilentlyContinue) { "supadiag" } else { "python -m supadiag" }
& $supadiagCmd service status >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Servico nao encontrado. Instalando..."
    & $supadiagCmd service install
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ERRO: Falha ao instalar servico no Agendador de Tarefas."
        Write-Host "Verifique se esta rodando como Administrador se necessario."
        Read-Host "Pressione Enter para sair"
        exit 1
    }
    Write-Host "Servico instalado com sucesso (executa na inicializacao do sistema)."
} else {
    Write-Host "Servico ja instalado."
}

# 6. Verifica Streamlit
Write-Host "[6/6] Verificando Streamlit..."
python -c "import streamlit" >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando Streamlit..."
    pip install streamlit
    if ($LASTEXITCODE -ne 0) {
        Write-Error "ERRO: Falha ao instalar Streamlit."
        Read-Host "Pressione Enter para sair"
        exit 1
    }
}
Write-Host "Streamlit OK."

Write-Host ""
Write-Host "=========================================="
Write-Host "  Iniciando SupaDiag"
Write-Host "=========================================="
Write-Host ""

# Testa conexao Supabase antes de iniciar
& $supadiagCmd check
if ($LASTEXITCODE -ne 0) {
    Write-Warning "AVISO: Conexao com Supabase falhou. Verifique .env e rede."
    Write-Host "O monitor tentara reconectar automaticamente."
    Write-Host ""
}

# Inicia monitor em janela separada
$venvPython = if (Test-Path "venv\Scripts\python.exe") { "$PSScriptRoot\venv\Scripts\python.exe" } else { "python" }
Write-Host "Iniciando coleta de metricas (monitor)..."
Start-Process "cmd.exe" -ArgumentList "/c", "$venvPython -m supadiag monitor" -WindowStyle Normal

# Abre dashboard Streamlit em outra janela
Write-Host "Abrindo dashboard Streamlit (http://localhost:8501)..."
Start-Process "cmd.exe" -ArgumentList "/c", "streamlit run dashboard.py --server.port 8501 --server.headless true" -WindowStyle Normal

Write-Host ""
Write-Host "SupaDiag iniciado com sucesso!"
Write-Host ""
Write-Host "- Monitor rodando em janela separada (coleta conforme frequência de cada máquina)"
Write-Host "- Dashboard Streamlit: http://localhost:8501"
Write-Host "- Servico agendado no Windows Task Scheduler (inicia na inicializacao)"
Write-Host "- Ver diario: supadiag diary"
Write-Host "- Parar monitor: feche a janela 'SupaDiag Monitor'"
Write-Host ""
Read-Host "Pressione Enter para sair"