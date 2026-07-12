"""Pruebas de contratos JSON Schema para extracciones futuras."""

import json

from app.contracts import (
    DOCUMENT_EXTRACTION_SCHEMA,
    INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA,
    POLICY_MATRIX_EXTRACTION_SCHEMA,
)
from app.contracts.common import (
    CONFIDENCE_VALUES,
    EVIDENCE_SCHEMA,
    EXTRACTION_BASIS_VALUES,
)
from app.contracts.document_extraction import FINDING_TYPE_VALUES


def _properties(schema: dict) -> dict:
    return schema["properties"]


def test_contracts_are_json_serializable() -> None:
    for schema in (
        DOCUMENT_EXTRACTION_SCHEMA,
        INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA,
        POLICY_MATRIX_EXTRACTION_SCHEMA,
    ):
        encoded = json.dumps(schema, ensure_ascii=False)
        assert encoded.startswith("{")


def test_common_evidence_contract_supports_pdf_and_excel_locations() -> None:
    properties = _properties(EVIDENCE_SCHEMA)

    assert "quote" in EVIDENCE_SCHEMA["required"]
    assert properties["quote"]["maxLength"] == 500
    assert properties["page_number"]["type"] == ["integer", "null"]
    assert properties["sheet_name"]["type"] == ["string", "null"]
    assert properties["row_reference"]["type"] == ["string", "null"]
    assert properties["confidence"]["enum"] == CONFIDENCE_VALUES
    assert "inferencia_contextual" not in properties["evidence_type"]["enum"]


def test_document_extraction_required_fields_and_zero_many_findings() -> None:
    assert DOCUMENT_EXTRACTION_SCHEMA["required"] == [
        "document_analysis",
        "findings",
        "evidence",
    ]
    findings = _properties(DOCUMENT_EXTRACTION_SCHEMA)["findings"]
    assert findings["type"] == "array"
    assert findings["minItems"] == 0

    analysis_required = _properties(DOCUMENT_EXTRACTION_SCHEMA)["document_analysis"][
        "required"
    ]
    assert "temporary_id" in analysis_required
    assert "preliminary_topics" in analysis_required
    assert "evidence_ids" in analysis_required


def test_document_finding_uses_only_functional_general_categories() -> None:
    expected = [
        "desarrollo_tecnologico",
        "decision_regulatoria",
        "consulta_publica",
        "propuesta_regulatoria",
        "asignacion_o_planificacion",
        "estudio_o_evidencia",
        "riesgo",
        "oportunidad",
        "posicion_institucional",
        "otro",
    ]
    assert FINDING_TYPE_VALUES == expected

    finding_schema = _properties(DOCUMENT_EXTRACTION_SCHEMA)["findings"]["items"]
    finding_properties = _properties(finding_schema)
    assert finding_properties["finding_type"]["enum"] == expected
    assert "recommended_follow_up" not in finding_properties
    assert "pmge_line" not in finding_properties
    assert "strategic_topic" not in finding_properties


def test_document_extraction_does_not_use_closed_topic_taxonomies() -> None:
    analysis_properties = _properties(
        _properties(DOCUMENT_EXTRACTION_SCHEMA)["document_analysis"]
    )
    finding_properties = _properties(
        _properties(DOCUMENT_EXTRACTION_SCHEMA)["findings"]["items"]
    )

    for properties in (analysis_properties, finding_properties):
        assert "strategic_topic" not in properties
        assert "pmge_line" not in properties
        assert "agenda_input_type" not in properties
        assert "enum" not in properties["preliminary_topics"]["items"]


def test_confidence_and_extraction_basis_enums_are_consistent() -> None:
    schemas = [
        _properties(DOCUMENT_EXTRACTION_SCHEMA)["document_analysis"],
        _properties(DOCUMENT_EXTRACTION_SCHEMA)["findings"]["items"],
        _properties(INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA)["pmge_projects"]["items"],
        _properties(POLICY_MATRIX_EXTRACTION_SCHEMA)["activities"]["items"],
    ]

    for schema in schemas:
        properties = _properties(schema)
        assert properties["confidence"]["enum"] == CONFIDENCE_VALUES
        assert properties["extraction_basis"]["enum"] == EXTRACTION_BASIS_VALUES


def test_institutional_plan_separates_pmge_and_regulatory_agenda() -> None:
    properties = _properties(INSTITUTIONAL_PLAN_EXTRACTION_SCHEMA)

    assert "pmge_projects" in properties
    assert "objectives" in properties
    assert "activities" in properties
    assert "regulatory_agenda_initiatives" in properties
    assert "regulatory_agenda_deliverables" in properties
    assert properties["pmge_projects"]["type"] == "array"
    assert properties["regulatory_agenda_initiatives"]["type"] == "array"
    assert properties["pmge_projects"] != properties["regulatory_agenda_initiatives"]


def test_policy_matrix_has_policies_activities_commitments_and_evidence() -> None:
    assert POLICY_MATRIX_EXTRACTION_SCHEMA["required"] == [
        "policies",
        "activities",
        "commitments",
        "evidence",
    ]
    properties = _properties(POLICY_MATRIX_EXTRACTION_SCHEMA)

    for key in ("policies", "activities", "commitments", "evidence"):
        assert properties[key]["type"] == "array"
        assert properties[key]["minItems"] == 0

    activity_properties = _properties(properties["activities"]["items"])
    assert "temporary_id" in properties["activities"]["items"]["required"]
    assert "evidence_ids" in properties["activities"]["items"]["required"]
    assert "commitments" in activity_properties
