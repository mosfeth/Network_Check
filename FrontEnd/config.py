# FrontEnd/config.py
# Configuração do FrontEnd - lê variáveis do .env do projeto raiz

import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env do diretório raiz do projeto
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

class FrontendSettings:
    """Configurações para o FrontEnd Streamlit."""
    
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
    SUPABASE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    
    # Configurações de exibição
    PAGE_TITLE: str = "NetPulse"
    PAGE_ICON: str = "🌐"
    LAYOUT: str = "wide"
    
    # Limites de consulta
    MAX_MEASUREMENTS: int = 500
    DEFAULT_HOURS: int = 24
    
    @classmethod
    def validate(cls) -> bool:
        """Valida se as configurações obrigatórias estão presentes."""
        return bool(cls.SUPABASE_URL and cls.SUPABASE_KEY)


settings = FrontendSettings()