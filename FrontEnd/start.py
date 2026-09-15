# FrontEnd/start.py
# Script para iniciar o FrontEnd Streamlit (usa venv isolado)

import subprocess
import sys
from pathlib import Path

def main():
    frontend_dir = Path(__file__).parent
    app_path = frontend_dir / "app.py"
    venv_python = frontend_dir / "venv" / "Scripts" / "python.exe"
    
    if not app_path.exists():
        print(f"Erro: {app_path} não encontrado")
        sys.exit(1)
    
    if not venv_python.exists():
        print(f"Erro: venv não encontrado em {venv_python}")
        print("Execute: python -m venv venv && venv\\Scripts\\pip install -r requirements.txt")
        sys.exit(1)
    
    print("Iniciando FrontEnd Streamlit (venv isolado)...")
    print("Acesse: http://localhost:8502")
    
    # Executa streamlit usando o python do venv
    subprocess.run([
        str(venv_python), "-m", "streamlit", "run", str(app_path),
        "--server.port", "8502",
        "--server.headless", "true"
    ])


if __name__ == "__main__":
    main()