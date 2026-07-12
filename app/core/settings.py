"""Configuracion pasiva de la aplicacion.

Este modulo introduce una capa de settings para la migracion a monolito
modular. Importarlo no crea directorios ni abre conexiones externas.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Configuracion inmutable leida desde entorno y archivo .env."""

    project_root: Path
    data_dir: Path
    output_dir: Path
    llm_provider: str
    gemini_api_key: str
    gemini_model: str
    openai_api_key: str
    openai_model: str
    supabase_url: str
    supabase_key: str

    @property
    def extracted_text_dir(self) -> Path:
        return self.output_dir / "extracted_text"

    @property
    def structured_data_dir(self) -> Path:
        return self.output_dir / "structured_data"

    @property
    def figures_dir(self) -> Path:
        return self.output_dir / "figures"

    @property
    def logs_dir(self) -> Path:
        return self.output_dir / "logs"


def resolve_project_path(value: str, project_root: Path = PROJECT_ROOT) -> Path:
    """Resuelve rutas relativas contra la raiz del proyecto."""
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (project_root / path).resolve()


def load_settings(
    *,
    project_root: Path = PROJECT_ROOT,
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Carga settings sin producir efectos secundarios de infraestructura."""
    env_path = env_file if env_file is not None else project_root / ".env"
    load_dotenv(env_path, override=False)
    source = environ if environ is not None else os.environ

    return Settings(
        project_root=project_root.resolve(),
        data_dir=resolve_project_path(
            source.get("DATA_DIR", "../Vigilanciatecnologica_data"), project_root
        ),
        output_dir=resolve_project_path(source.get("OUTPUT_DIR", "outputs"), project_root),
        llm_provider=source.get("LLM_PROVIDER", "gemini"),
        gemini_api_key=source.get("GEMINI_API_KEY", ""),
        gemini_model=source.get("GEMINI_MODEL", "gemini-2.5-flash"),
        openai_api_key=source.get("OPENAI_API_KEY", ""),
        openai_model=source.get("OPENAI_MODEL", "gpt-4o-mini"),
        supabase_url=source.get("SUPABASE_URL", ""),
        supabase_key=source.get("SUPABASE_KEY", ""),
    )
