"""Pruebas de lógica del dashboard sin iniciar un servidor."""

import pandas as pd

from app.dashboard import _metric_values, apply_filters, parse_list


def test_parse_list_supports_json_and_python_literals() -> None:
    assert parse_list('["5G", "6G"]') == ["5G", "6G"]
    assert parse_list("['ITU', 'GSMA']") == ["ITU", "GSMA"]
    assert parse_list("valor inválido") == []


def test_apply_filters_combines_scalar_and_list_filters() -> None:
    dataframe = pd.DataFrame(
        [
            {
                "source_folder": "CRC",
                "relevancia_agenda_ane": "Alta",
                "tipo_documento": "Reporte",
                "tecnologias": '["5G", "NTN"]',
                "paises": '["Colombia"]',
                "organizaciones": '["CRC"]',
            },
            {
                "source_folder": "GSMA",
                "relevancia_agenda_ane": "Media",
                "tipo_documento": "Informe",
                "tecnologias": '["6G"]',
                "paises": '["Francia"]',
                "organizaciones": '["GSMA"]',
            },
        ]
    )
    filters = {
        "source_folder": ["CRC"],
        "relevancia_agenda_ane": [],
        "tipo_documento": [],
        "tecnologias": ["5G"],
        "paises": ["Colombia"],
        "organizaciones": [],
    }

    result = apply_filters(dataframe, filters)

    assert len(result) == 1
    assert result.iloc[0]["source_folder"] == "CRC"


def test_metrics_count_unique_physical_documents() -> None:
    corpus = pd.DataFrame(
        {
            "file_path": ["a.xlsx", "a.xlsx", "b.pdf"],
            "source_folder": ["Fuente A", "Fuente A", "Fuente B"],
        }
    )
    structured = pd.DataFrame({"llm_status": ["ok", "error"]})
    count_table = pd.DataFrame({"value": ["5G"], "count": [3]})
    data = {
        "document_texts": corpus,
        "structured_documents": structured,
        "technologies": count_table,
        "bands": pd.DataFrame({"value": ["700 MHz"], "count": [2]}),
        "relevance": pd.DataFrame({"value": ["Alta"], "count": [1]}),
    }

    metrics = _metric_values(data)

    assert metrics["unique_documents"] == 2
    assert metrics["rows"] == 3
    assert metrics["llm_ok_percentage"] == 50.0
    assert metrics["top_source"] == "Fuente A"
