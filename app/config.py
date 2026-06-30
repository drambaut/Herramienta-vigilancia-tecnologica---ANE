"""Configuración central de rutas del proyecto."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _project_path(value: str) -> Path:
    """Convierte una ruta relativa al proyecto en una ruta resuelta."""
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


DATA_DIR = _project_path(os.getenv("DATA_DIR", "../Vigilanciatecnologica_data"))
OUTPUT_DIR = _project_path(os.getenv("OUTPUT_DIR", "outputs"))
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

EXTRACTED_TEXT_DIR = OUTPUT_DIR / "extracted_text"
STRUCTURED_DATA_DIR = OUTPUT_DIR / "structured_data"
FIGURES_DIR = OUTPUT_DIR / "figures"
LOGS_DIR = OUTPUT_DIR / "logs"

for directory in (
    OUTPUT_DIR,
    EXTRACTED_TEXT_DIR,
    STRUCTURED_DATA_DIR,
    FIGURES_DIR,
    LOGS_DIR,
):
    directory.mkdir(parents=True, exist_ok=True)
