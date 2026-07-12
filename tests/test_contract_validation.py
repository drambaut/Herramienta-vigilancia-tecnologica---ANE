"""Pruebas de validacion JSON Schema para contratos de extraccion."""

import copy

import pytest

from app.contracts.validation import (
    ContractValidationError,
    validate_document_extraction,
    validate_institutional_plan_extraction,
    validate_policy_matrix_extraction,
)


def evidence() -> dict:
    return {
        "temporary_id": "ev-1",
        "quote": "Texto fuente breve.",
        "evidence_type": "cita_textual",
        "page_number": 1,
        "sheet_name": None,
        "row_reference": None,
        "section_title": "Seccion",
        "confidence": "Alta",
    }


def document_payload() -> dict:
    return {
        "document_analysis": {
            "temporary_id": "analysis-1",
            "document_type": "reporte",
            "title": "Documento de prueba",
            "summary": "Resumen.",
            "preliminary_topics": ["6 GHz"],
            "technologies": ["Wi-Fi"],
            "frequency_bands": ["6 GHz"],
            "countries_regions": ["Colombia"],
            "organizations": ["ANE"],
            "actors": ["regulador"],
            "keywords": ["espectro"],
            "confidence": "Alta",
            "extraction_basis": "explicit",
            "evidence_ids": ["ev-1"],
        },
        "findings": [
            {
                "temporary_id": "finding-1",
                "finding_type": "decision_regulatoria",
                "title": "Decision",
                "description": "Descripcion.",
                "preliminary_topics": ["uso de espectro"],
                "technologies": [],
                "frequency_bands": ["6 GHz"],
                "countries_regions": [],
                "organizations": ["ANE"],
                "confidence": "Media",
                "extraction_basis": "mixed",
                "evidence_ids": ["ev-1"],
            }
        ],
        "evidence": [evidence()],
    }


def institutional_payload() -> dict:
    return {
        "pmge_projects": [
            {
                "temporary_id": "project-1",
                "project_name": "Proyecto PMGE",
                "description": "Descripcion.",
                "objectives": ["Objetivo"],
                "activities": ["Actividad"],
                "expected_outputs": ["Producto"],
                "period": "2026",
                "responsible_area": None,
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "objectives": [
            {
                "temporary_id": "objective-1",
                "objective_text": "Objetivo",
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "activities": [],
        "regulatory_agenda_initiatives": [
            {
                "temporary_id": "initiative-1",
                "initiative_name": "Iniciativa",
                "regulatory_objective": "Objetivo regulatorio",
                "deliverables": ["Entregable"],
                "period": "2027",
                "responsible_area": None,
                "confidence": "Media",
                "extraction_basis": "mixed",
                "evidence_ids": ["ev-1"],
            }
        ],
        "regulatory_agenda_deliverables": [
            {
                "temporary_id": "deliverable-1",
                "initiative_temporary_id": "initiative-1",
                "deliverable_name": "Entregable",
                "description": None,
                "period": "2027",
                "confidence": "Media",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "evidence": [evidence()],
    }


def policy_payload() -> dict:
    return {
        "policies": [
            {
                "temporary_id": "policy-1",
                "policy_name": "Politica",
                "instrument_name": "Instrumento",
                "policy_axis": "Eje",
                "description": "Descripcion",
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "activities": [
            {
                "temporary_id": "activity-1",
                "policy_temporary_id": "policy-1",
                "activity_name": "Actividad",
                "activity_description": "Descripcion",
                "responsible_area": "Area",
                "execution_period": "2026",
                "commitments": ["Compromiso"],
                "keywords": ["politica"],
                "confidence": "Alta",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "commitments": [
            {
                "temporary_id": "commitment-1",
                "policy_activity_temporary_id": "activity-1",
                "commitment_text": "Compromiso",
                "responsible_area": "Area",
                "period": "2026",
                "confidence": "Media",
                "extraction_basis": "explicit",
                "evidence_ids": ["ev-1"],
            }
        ],
        "evidence": [evidence()],
    }


def assert_invalid(payload: dict, validator, expected: str) -> str:
    with pytest.raises(ContractValidationError) as exc_info:
        validator(payload)
    message = str(exc_info.value)
    assert expected in message
    return message


def test_minimal_valid_payloads_for_each_contract() -> None:
    assert validate_document_extraction(document_payload()) == document_payload()
    assert validate_institutional_plan_extraction(institutional_payload()) == institutional_payload()
    assert validate_policy_matrix_extraction(policy_payload()) == policy_payload()


def test_missing_required_field_is_rejected_with_readable_path() -> None:
    payload = document_payload()
    del payload["document_analysis"]["title"]

    message = assert_invalid(payload, validate_document_extraction, "DocumentExtraction.document_analysis")
    assert "campo obligatorio ausente: 'title'" in message
    assert "rule=required" in message


def test_invalid_confidence_is_rejected_with_nested_path() -> None:
    payload = document_payload()
    payload["findings"][0]["confidence"] = "Muy alta"

    message = assert_invalid(
        payload,
        validate_document_extraction,
        "DocumentExtraction.findings[0].confidence",
    )
    assert "'Muy alta' is not one of ['Alta', 'Media', 'Baja']" in message
    assert "rule=enum" in message


def test_invalid_extraction_basis_is_rejected() -> None:
    payload = policy_payload()
    payload["activities"][0]["extraction_basis"] = "contextual"

    message = assert_invalid(
        payload,
        validate_policy_matrix_extraction,
        "PolicyMatrixExtraction.activities[0].extraction_basis",
    )
    assert "contextual" in message
    assert "rule=enum" in message


def test_quote_longer_than_500_characters_is_rejected() -> None:
    payload = institutional_payload()
    payload["evidence"][0]["quote"] = "x" * 501

    message = assert_invalid(
        payload,
        validate_institutional_plan_extraction,
        "InstitutionalPlanExtraction.evidence[0].quote",
    )
    assert "too long" in message
    assert "rule=maxLength" in message


def test_additional_property_is_rejected() -> None:
    payload = document_payload()
    payload["document_analysis"]["unexpected"] = "no permitido"

    message = assert_invalid(
        payload,
        validate_document_extraction,
        "DocumentExtraction.document_analysis",
    )
    assert "propiedad adicional no permitida" in message
    assert "unexpected" in message
    assert "rule=additionalProperties" in message


def test_wrong_evidence_ids_type_is_rejected() -> None:
    payload = copy.deepcopy(policy_payload())
    payload["activities"][0]["evidence_ids"] = "ev-1"

    message = assert_invalid(
        payload,
        validate_policy_matrix_extraction,
        "PolicyMatrixExtraction.activities[0].evidence_ids",
    )
    assert "is not of type 'array'" in message
    assert "rule=type" in message


def test_wrong_nested_field_type_is_rejected() -> None:
    payload = document_payload()
    payload["findings"][0]["technologies"] = "5G"

    message = assert_invalid(
        payload,
        validate_document_extraction,
        "DocumentExtraction.findings[0].technologies",
    )
    assert "is not of type 'array'" in message
