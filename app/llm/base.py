"""Interfaces base para clientes LLM estructurados."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class LLMClient(Protocol):
    """Cliente capaz de devolver JSON estructurado."""

    @property
    def model_name(self) -> str:
        """Nombre del modelo usado por el cliente."""

    def generate_json(
        self,
        *,
        prompt: str,
        content: str,
        response_schema: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Ejecuta una extraccion y devuelve un diccionario JSON."""
