"""Pruebas del servicio LLM modular sin llamadas reales."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.settings import Settings
from app.llm.errors import (
    EmptyLLMResponseError,
    InvalidLLMJSONError,
    LLMProviderError,
    MissingConfigurationError,
)
from app.llm.gemini_client import GeminiStructuredClient
from app.llm.service import StructuredExtractionService


def evidence() -> dict:
    return {
        "temporary_id": "ev-1",
        "quote": "Texto fuente.",
        "evidence_type": "cita_textual",
        "page_number": 1,
        "sheet_name": None,
        "row_reference": None,
        "section_title": "Seccion",
        "confidence": "Alta",
    }


def document_payload(confidence: str = "Alta") -> dict:
    return {
        "document_analysis": {
            "temporary_id": "analysis-1",
            "document_type": "reporte",
            "title": "Documento",
            "summary": "Resumen",
            "preliminary_topics": [],
            "technologies": [],
            "frequency_bands": [],
            "countries_regions": [],
            "organizations": [],
            "actors": [],
            "keywords": [],
            "confidence": "Alta",
            "extraction_basis": "explicit",
            "evidence_ids": ["ev-1"],
        },
        "findings": [
            {
                "temporary_id": "finding-1",
                "finding_type": "estudio_o_evidencia",
                "title": "Hallazgo",
                "description": "Descripcion",
                "preliminary_topics": [],
                "technologies": [],
                "frequency_bands": [],
                "countries_regions": [],
                "organizations": [],
                "confidence": confidence,
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "evidence": [evidence()],
    }


def institutional_payload() -> dict:
    return {
        "pmge_projects": [],
        "objectives": [],
        "activities": [],
        "regulatory_agenda_initiatives": [],
        "regulatory_agenda_deliverables": [],
        "evidence": [],
    }


def policy_payload() -> dict:
    return {
        "policies": [],
        "activities": [],
        "commitments": [],
        "evidence": [],
    }


class FakeClient:
    model_name = "fake-model"

    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or document_payload()
        self.calls: list[dict] = []

    def generate_json(self, *, prompt: str, content: str, response_schema: dict) -> dict:
        self.calls.append(
            {"prompt": prompt, "content": content, "response_schema": response_schema}
        )
        return self.payload


def settings(api_key: str = "fake-key") -> Settings:
    root = Path(__file__).resolve().parents[1]
    return Settings(
        project_root=root,
        data_dir=root / "data",
        output_dir=root / "outputs",
        llm_provider="gemini",
        gemini_api_key=api_key,
        gemini_model="gemini-test",
        openai_api_key="",
        openai_model="",
        supabase_url="",
        supabase_key="",
    )


def test_service_selects_prompt_and_schema() -> None:
    client = FakeClient(document_payload())
    service = StructuredExtractionService(client=client)

    result = service.extract(
        prompt_id="document_extraction", version="v1", content="contenido"
    )

    assert result.prompt_id == "document_extraction"
    assert result.prompt_version == "v1"
    assert result.contract_name == "DocumentExtraction"
    assert result.model_name == "fake-model"
    assert client.calls[0]["response_schema"]["title"] == "DocumentExtraction"
    assert "JSON Schema DocumentExtraction" in client.calls[0]["prompt"]
    assert client.calls[0]["content"] == "contenido"


@pytest.mark.parametrize(
    ("prompt_id", "payload", "contract"),
    [
        ("document_extraction", document_payload(), "DocumentExtraction"),
        ("institutional_plan_extraction", institutional_payload(), "InstitutionalPlanExtraction"),
        ("policy_matrix_extraction", policy_payload(), "PolicyMatrixExtraction"),
    ],
)
def test_service_accepts_valid_responses(prompt_id: str, payload: dict, contract: str) -> None:
    result = StructuredExtractionService(client=FakeClient(payload)).extract(
        prompt_id=prompt_id, version="v1", content="texto"
    )

    assert result.payload == payload
    assert result.contract_name == contract


def test_service_rejects_invalid_response() -> None:
    service = StructuredExtractionService(client=FakeClient(document_payload("Muy alta")))

    with pytest.raises(Exception, match="DocumentExtraction.findings\\[0\\].confidence"):
        service.extract(prompt_id="document_extraction", version="v1", content="texto")


def test_missing_prompt_fails() -> None:
    with pytest.raises(KeyError):
        StructuredExtractionService(client=FakeClient()).extract(
            prompt_id="no_existe", version="v1", content="texto"
        )


def test_gemini_missing_api_key_is_rejected() -> None:
    client = GeminiStructuredClient(settings=settings(api_key=""))

    with pytest.raises(MissingConfigurationError):
        client.generate_json(prompt="p", content="c", response_schema={"type": "object"})


def test_gemini_empty_response_is_rejected() -> None:
    fake_google = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kwargs: SimpleNamespace(text="")
        )
    )
    client = GeminiStructuredClient(
        settings=settings(), client_factory=lambda **kwargs: fake_google
    )

    with pytest.raises(EmptyLLMResponseError):
        client.generate_json(prompt="p", content="c", response_schema={"type": "object"})


def test_gemini_malformed_json_is_rejected() -> None:
    fake_google = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kwargs: SimpleNamespace(text="{mal")
        )
    )
    client = GeminiStructuredClient(
        settings=settings(), client_factory=lambda **kwargs: fake_google
    )

    with pytest.raises(InvalidLLMJSONError):
        client.generate_json(prompt="p", content="c", response_schema={"type": "object"})


def test_gemini_provider_error_is_wrapped() -> None:
    def fail(**kwargs):
        raise RuntimeError("boom")

    fake_google = SimpleNamespace(models=SimpleNamespace(generate_content=fail))
    client = GeminiStructuredClient(
        settings=settings(), client_factory=lambda **kwargs: fake_google
    )

    with pytest.raises(LLMProviderError, match="boom"):
        client.generate_json(prompt="p", content="c", response_schema={"type": "object"})


def test_gemini_client_is_created_lazily() -> None:
    calls: list[str] = []

    def factory(**kwargs):
        calls.append(kwargs["api_key"])
        return SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **call: SimpleNamespace(text='{"ok": true}')
            )
        )

    client = GeminiStructuredClient(settings=settings(), client_factory=factory)
    assert calls == []

    result = client.generate_json(
        prompt="p", content="c", response_schema={"type": "object"}
    )

    assert result == {"ok": True}
    assert calls == ["fake-key"]
