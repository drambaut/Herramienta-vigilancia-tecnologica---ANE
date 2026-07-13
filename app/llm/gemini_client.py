"""Cliente Gemini para respuestas JSON con schema."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from app.core.settings import Settings, load_settings
from app.llm.base import LLMInput
from app.llm.errors import (
    EmptyLLMResponseError,
    InvalidLLMJSONError,
    LLMProviderError,
    MissingConfigurationError,
)


class GeminiStructuredClient:
    """Encapsula google-genai y crea el cliente solo al ejecutar solicitudes."""

    def __init__(
        self,
        settings: Settings | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._settings = settings or load_settings()
        self._client_factory = client_factory
        self._client: Any | None = None

    @property
    def model_name(self) -> str:
        return self._settings.gemini_model

    def _get_client(self) -> Any:
        if not self._settings.gemini_api_key.strip():
            raise MissingConfigurationError("GEMINI_API_KEY no esta configurada.")
        if self._client is None:
            if self._client_factory is None:
                from google import genai

                self._client_factory = genai.Client
            self._client = self._client_factory(api_key=self._settings.gemini_api_key)
        return self._client

    def generate_json(
        self,
        *,
        prompt: str,
        input_data: LLMInput,
        response_schema: Mapping[str, Any],
    ) -> dict[str, Any]:
        try:
            from google.genai import types

            response = self._get_client().models.generate_content(
                model=self._settings.gemini_model,
                contents=self._build_contents(types, prompt, input_data),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=dict(response_schema),
                    temperature=0.1,
                ),
            )
        except MissingConfigurationError:
            raise
        except Exception as exc:
            raise LLMProviderError(f"Error del proveedor Gemini: {exc}") from exc

        raw_text = getattr(response, "text", None)
        if not raw_text or not str(raw_text).strip():
            raise EmptyLLMResponseError("Gemini devolvio una respuesta vacia.")

        try:
            parsed = json.loads(str(raw_text))
        except json.JSONDecodeError as exc:
            raise InvalidLLMJSONError(f"Gemini devolvio JSON invalido: {exc}") from exc
        if not isinstance(parsed, dict):
            raise InvalidLLMJSONError("Gemini devolvio JSON valido pero no un objeto.")
        return parsed

    def _build_contents(self, types: Any, prompt: str, input_data: LLMInput) -> list[Any]:
        text = self._build_text_part(prompt, input_data)
        parts = [types.Part.from_text(text=text)]
        if input_data.file_bytes is not None:
            parts.append(
                types.Part.from_bytes(
                    data=input_data.file_bytes,
                    mime_type=input_data.mime_type or "application/octet-stream",
                )
            )
        return parts

    def _build_text_part(self, prompt: str, input_data: LLMInput) -> str:
        metadata = "\n".join(
            f"- {key}: {value}" for key, value in sorted(input_data.metadata.items())
        )
        sections = [prompt.rstrip()]
        if metadata:
            sections.append(f"METADATOS:\n{metadata}")
        if input_data.file_name:
            sections.append(f"ARCHIVO: {input_data.file_name}")
        if input_data.text.strip():
            sections.append(f"CONTENIDO A ANALIZAR:\n{input_data.text}")
        return "\n\n".join(sections)
