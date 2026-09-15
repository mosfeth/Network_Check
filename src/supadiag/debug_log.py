import logging
import sys
from pathlib import Path
from datetime import datetime

# Configurar logging para arquivo
log_file = Path(__file__).resolve().parents[2] / "debug_tui.log"

# Handler para arquivo
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)

# Handler para console (opcional)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
console_handler.setFormatter(console_formatter)

# Logger raiz
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

# Logger específico do módulo
logger = logging.getLogger("supadiag.tui")
logger.setLevel(logging.DEBUG)

def log_exception(logger, msg: str, exc: Exception):
    """Loga exceção com traceback completo."""
    logger.exception(f"{msg}: {exc}")