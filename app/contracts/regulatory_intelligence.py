"""Contrato para inteligencia regulatoria transversal."""

from app.contracts.common import (
    CONFIDENCE,
    EVIDENCE_IDS,
    EXTRACTION_BASIS,
    OPEN_TEXT_LIST,
    TEMPORARY_ID,
    array_of,
)

RELATIONSHIP_TYPE_VALUES = [
    "covered",
    "partially_covered",
    "gap",
    "complementary",
    "tension",
    "no_direct_relation",
]

ID_LIST = {"type": "array", "items": {"type": "string", "minLength": 1}}

REGULATORY_INTELLIGENCE_ITEM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "temporary_id",
        "international_situation",
        "regulatory_debate",
        "countries_regions",
        "organizations",
        "agenda_item_ids",
        "relationship_type",
        "coverage_explanation",
        "implications_for_ane",
        "finding_ids",
        "evidence_ids",
        "confidence",
        "extraction_basis",
    ],
    "oneOf": [
        {"required": ["theme_id"], "not": {"required": ["theme_temporary_id"]}},
        {"required": ["theme_temporary_id"], "not": {"required": ["theme_id"]}},
    ],
    "properties": {
        "temporary_id": TEMPORARY_ID,
        "theme_id": {"type": "string", "minLength": 1},
        "theme_temporary_id": {"type": "string", "minLength": 1},
        "international_situation": {"type": "string"},
        "regulatory_debate": {"type": "string"},
        "countries_regions": OPEN_TEXT_LIST,
        "organizations": OPEN_TEXT_LIST,
        "agenda_item_ids": ID_LIST,
        "relationship_type": {"type": "string", "enum": RELATIONSHIP_TYPE_VALUES},
        "coverage_explanation": {"type": "string"},
        "implications_for_ane": {"type": "string"},
        "finding_ids": ID_LIST,
        "evidence_ids": EVIDENCE_IDS,
        "confidence": CONFIDENCE,
        "extraction_basis": EXTRACTION_BASIS,
    },
}

REGULATORY_INTELLIGENCE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "RegulatoryIntelligence",
    "type": "object",
    "additionalProperties": False,
    "required": ["analyses", "overall_gaps", "evidence_ids"],
    "properties": {
        "analyses": array_of(REGULATORY_INTELLIGENCE_ITEM_SCHEMA, min_items=0),
        "overall_gaps": OPEN_TEXT_LIST,
        "evidence_ids": EVIDENCE_IDS,
    },
}
