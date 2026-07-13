"""Servicio de extraccion estructurada con prompts versionados."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts.document_extraction import DOCUMENT_EXTRACTION_SCHEMA
from app.contracts.institutional_plan import INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA
from app.contracts.policy_matrix import POLICY_MATRIX_EXTRACTION_SCHEMA
from app.contracts.validation import (
    validate_document_extraction,
    validate_institutional_plan_extraction,
    validate_policy_matrix_extraction,
)
from app.llm.base import LLMClient, LLMInput
from app.llm.errors import InvalidContractError
from app.llm.gemini_client import GeminiStructuredClient
from app.prompting import load_prompt


SCHEMA_BY_CONTRACT: dict[str, dict[str, Any]] = {
    "DocumentExtraction": DOCUMENT_EXTRACTION_SCHEMA,
    "InstitutionalPlanExtraction": INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA,
    "PolicyMatrixExtraction": POLICY_MATRIX_EXTRACTION_SCHEMA,
}

VALIDATOR_BY_CONTRACT = {
    "DocumentExtraction": validate_document_extraction,
    "InstitutionalPlanExtraction": validate_institutional_plan_extraction,
    "PolicyMatrixExtraction": validate_policy_matrix_extraction,
}


@dataclass(frozen=True)
class ExtractionResult:
    payload: dict[str, Any]
    prompt_id: str
    prompt_version: str
    contract_name: str
    model_name: str


class StructuredExtractionService:
    """Orquesta prompt, schema, cliente LLM y validacion local."""

    def __init__(self, client: LLMClient | None = None) -> None:
        self._client = client or GeminiStructuredClient()

    def extract(
        self,
        *,
        prompt_id: str,
        version: str,
        input_data: LLMInput | str | None = None,
        content: str | None = None,
    ) -> ExtractionResult:
        """Ejecuta extraccion.

        Compatibilidad transitoria: content o input_data=str se convierten a LLMInput.
        """
        spec, prompt = load_prompt(prompt_id, version)
        schema = SCHEMA_BY_CONTRACT.get(spec.contract)
        validator = VALIDATOR_BY_CONTRACT.get(spec.contract)
        if schema is None or validator is None:
            raise InvalidContractError(f"Contrato no soportado: {spec.contract}")

        normalized_input = self._normalize_input(input_data, content)
        payload = self._client.generate_json(
            prompt=prompt,
            input_data=normalized_input,
            response_schema=schema,
        )
        validated = validator(payload)
        return ExtractionResult(
            payload=dict(validated),
            prompt_id=spec.prompt_id,
            prompt_version=spec.version,
            contract_name=spec.contract,
            model_name=self._client.model_name,
        )

    def _normalize_input(
        self, input_data: LLMInput | str | None, content: str | None
    ) -> LLMInput:
        if isinstance(input_data, LLMInput):
            return input_data
        if isinstance(input_data, str):
            return LLMInput(text=input_data)
        if content is not None:
            return LLMInput(text=content)
        return LLMInput()
