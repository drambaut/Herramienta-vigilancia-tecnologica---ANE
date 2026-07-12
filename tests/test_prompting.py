"""Pruebas para prompts especializados y versionados."""

from pathlib import Path

import pytest

import app.llm_extract as llm_module
from app.core.settings import PROJECT_ROOT
from app.prompting import PROMPT_REGISTRY, load_prompt
from app.prompting.registry import get_prompt_spec


V1_PROMPTS = {
    "document_extraction": "DocumentExtraction",
    "institutional_plan_extraction": "InstitutionalPlanExtraction",
    "policy_matrix_extraction": "PolicyMatrixExtraction",
}


def test_v1_prompt_files_exist() -> None:
    for prompt_id in V1_PROMPTS:
        spec = get_prompt_spec(prompt_id, "v1")
        assert (PROJECT_ROOT / spec.path).is_file()


def test_load_prompt_by_id_and_version() -> None:
    spec, content = load_prompt("document_extraction", "v1")

    assert spec.prompt_id == "document_extraction"
    assert spec.version == "v1"
    assert spec.status == "active"
    assert "Devuelve unicamente JSON valido" in content


def test_missing_prompt_fails_clearly() -> None:
    with pytest.raises(KeyError, match="No existe prompt registrado"):
        load_prompt("missing_prompt", "v1")


def test_registered_contracts_are_correct() -> None:
    contracts = {
        spec.prompt_id: spec.contract
        for spec in PROMPT_REGISTRY
        if spec.version == "v1"
    }

    assert contracts == V1_PROMPTS


def test_document_prompt_avoids_closed_strategic_taxonomy_references() -> None:
    _, content = load_prompt("document_extraction", "v1")

    assert "TEMAS_ESTRATEGICOS" not in content
    assert "LINEAS_PMGE" not in content
    assert "No asignes lineas PMGE" in content
    assert "No generes recomendaciones" in content


def test_prompts_include_required_json_evidence_and_confidence_instructions() -> None:
    for prompt_id in V1_PROMPTS:
        _, content = load_prompt(prompt_id, "v1")
        assert "JSON Schema" in content
        assert "response_schema" in content
        assert "Devuelve unicamente JSON valido" in content
        assert "temporary_id" in content
        assert "confidence unicamente con estos valores: Alta, Media o Baja" in content
        assert "extraction_basis unicamente con estos valores: explicit, inferred o mixed" in content
        assert "quote" in content
        assert "maximo 500 caracteres" in content
        assert "evidence" in content or "evidencia" in content


def test_institutional_plan_prompt_separates_pmge_and_agenda() -> None:
    _, content = load_prompt("institutional_plan_extraction", "v1")

    assert "PMGE" in content
    assert "Agenda Regulatoria" in content
    assert "Extrae por separado" in content
    assert "No cruces todavia" in content


def test_policy_matrix_prompt_preserves_excel_references() -> None:
    _, content = load_prompt("policy_matrix_extraction", "v1")

    assert "sheet_name" in content
    assert "row_reference" in content
    assert "No hagas alineacion" in content


def test_legacy_prompt_compatibility_is_preserved() -> None:
    legacy_path = PROJECT_ROOT / "prompts" / "legacy" / "extraction_prompt.txt"
    current_path = PROJECT_ROOT / "prompts" / "extraction_prompt.txt"

    assert legacy_path.is_file()
    assert current_path.is_file()
    assert llm_module.PROMPT_PATH == current_path
    assert legacy_path.read_text(encoding="utf-8") == current_path.read_text(
        encoding="utf-8"
    )
    legacy_spec, legacy_content = load_prompt("legacy_document_extraction", "legacy")
    assert legacy_spec.status == "legacy"
    assert legacy_content


def test_loader_does_not_modify_prompt_files() -> None:
    spec = get_prompt_spec("document_extraction", "v1")
    prompt_path = PROJECT_ROOT / spec.path
    before = Path(prompt_path).stat().st_mtime_ns

    load_prompt("document_extraction", "v1")

    after = Path(prompt_path).stat().st_mtime_ns
    assert after == before
