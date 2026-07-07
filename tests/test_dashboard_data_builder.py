"""Pruebas de la capa local de datos para la demo."""
from pathlib import Path
import pandas as pd
import pytest
import app.dashboard_data_builder as builder
from app.topic_taxonomy import infer_tema_estrategico, normalize_bands, normalize_technologies, parse_list_field

def test_taxonomy_parses_and_normalizes_variants() -> None:
    assert parse_list_field('["WiFi", "Direct-to-Device"]') == ["WiFi", "Direct-to-Device"]
    assert normalize_technologies(["WiFi", "Artificial Intelligence"]) == ["Wi-Fi", "IA"]
    assert normalize_bands(["6 GHz superior", "Ka-band"]) == ["upper 6 GHz", "banda Ka"]
    assert infer_tema_estrategico(["NTN"], [], "") == "Conectividad satelital, NTN y D2D"

def test_build_dashboard_data_creates_expected_demo_csvs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    structured = tmp_path / "outputs" / "structured_data"; demo = tmp_path / "demo_data"; structured.mkdir(parents=True)
    input_csv = structured / "structured_documents.csv"
    pd.DataFrame([{"document_id": "1", "file_name": "signal.pdf", "source_folder": "UIT", "file_type": "pdf", "tema_principal": "Consulta NTN", "tecnologias": '["Non-Terrestrial Networks", "WiFi"]', "bandas_frecuencia": '["6 GHz"]', "paises": '["Colombia"]', "organizaciones": '["UIT"]', "actores": '["Reguladores"]', "palabras_clave": '["consulta pública"]', "resumen": "Consulta sobre satélites", "relevancia_agenda_ane": "Alta", "justificacion_relevancia": "Prioridad ANE"}]).to_csv(input_csv, index=False, encoding="utf-8-sig")
    monkeypatch.setattr(builder, "INPUT_CSV", input_csv); monkeypatch.setattr(builder, "STRUCTURED_DATA_DIR", structured); monkeypatch.setattr(builder, "DEMO_DATA_DIR", demo)
    result = builder.build_dashboard_data()
    assert result["records_processed"] == 1
    assert {path.name for path in demo.iterdir()} == set(builder.OUTPUT_NAMES)
    records = pd.read_csv(demo / "dashboard_records.csv")
    assert records.loc[0, "tema_estrategico"] == "Conectividad satelital, NTN y D2D"
    assert records.loc[0, "relevancia_score"] == 10
    assert records.loc[0, "actividad_internacional_score"] == 3

def test_missing_input_has_actionable_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(builder, "INPUT_CSV", tmp_path / "missing.csv")
    with pytest.raises(FileNotFoundError, match="python app/llm_extract.py"): builder.build_dashboard_data()


def test_regulatory_datasets_have_complete_explanations() -> None:
    records = pd.DataFrame([
        {"document_id": "1", "tema_estrategico": "6 GHz, Wi-Fi e IMT", "senal_regulatoria": "Consulta upper 6 GHz", "tecnologias": '["Wi-Fi"]', "bandas_frecuencia": '["6 GHz"]', "tipo_insumo_agenda": "Seguimiento", "relevancia_label": "Alta", "relevancia_score": 8},
        {"document_id": "2", "tema_estrategico": "Conectividad satelital, NTN y D2D", "senal_regulatoria": "Reglas D2D", "tecnologias": '["D2D"]', "bandas_frecuencia": '[]', "tipo_insumo_agenda": "Nota técnica", "relevancia_label": "Alta", "relevancia_score": 9},
    ])
    regulatory_map = builder.build_regulatory_map(records)
    trends = builder.build_regulatory_trends(records)
    assert len(trends) == regulatory_map["tema_macro"].nunique() == 2
    assert not regulatory_map[["subtema", "debate_regulatorio", "implicacion_regulatoria"]].replace("", pd.NA).isna().any().any()
    required = ["nombre_tendencia", "de_que_trata", "que_esta_pasando", "por_que_importa", "implicacion_regulatoria"]
    assert not trends[required].replace("", pd.NA).isna().any().any()


def test_policy_matrix_activities_are_generated_with_required_columns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference = tmp_path / "reference"
    reference.mkdir()
    pd.DataFrame([{
        "Documento": "Política de espectro",
        "Objetivo": "Uso eficiente del espectro",
        "Acción o Actividad": "Evaluar 6 GHz para Wi-Fi y uso libre",
        "Plazo ejecución": "2026",
        "Responsable": "ANE",
    }]).to_excel(reference / "matriz_politicas_publicas.xlsx", index=False)
    monkeypatch.setattr(builder, "REFERENCE_DATA_DIR", reference)
    activities = builder.build_policy_matrix_activities()
    assert list(activities.columns) == builder.POLICY_ACTIVITY_COLUMNS
    assert len(activities) == 1
    assert activities.loc[0, "activity_name"] == "Evaluar 6 GHz para Wi-Fi y uso libre"
    assert "6 GHz" in activities.loc[0, "keywords"]


def test_pmge_projects_fallback_empty_has_required_columns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference = tmp_path / "reference"
    reference.mkdir()
    monkeypatch.setattr(builder, "REFERENCE_DATA_DIR", reference)
    projects = builder.build_pmge_projects()
    assert list(projects.columns) == builder.PMGE_PROJECT_COLUMNS
    assert projects.empty


def test_alignment_outputs_columns_scores_values_and_support_documents() -> None:
    activities = pd.DataFrame([{
        "activity_id": "ACT-001", "policy_name": "Política de espectro", "instrument_name": "Política",
        "policy_axis": "Uso eficiente", "activity_name": "Evaluar 6 GHz para Wi-Fi",
        "activity_description": "Uso libre no licenciado en 6 GHz", "responsible_area": "ANE",
        "execution_period": "2026", "keywords": "6 GHz Wi-Fi uso libre",
    }])
    records = pd.DataFrame([{
        "document_id": "1", "file_name": "consulta-6ghz-2026.pdf", "source_folder": "CRC",
        "tema_estrategico": "6 GHz, Wi-Fi e IMT", "tipo_insumo_agenda": "Nota técnica",
    }])
    trends = pd.DataFrame([{
        "tema_macro": "6 GHz, Wi-Fi e IMT", "nombre_tendencia": "Uso libre de 6 GHz",
        "de_que_trata": "Wi-Fi y uso no licenciado", "que_esta_pasando": "Hay consultas sobre 6 GHz",
        "implicacion_regulatoria": "Definir condiciones", "relevancia_score_promedio": 9,
        "tipo_insumo_principal": "Nota técnica",
    }])
    document_alignment = builder.build_document_policy_alignment(trends, records, pd.DataFrame(), activities)
    assert list(document_alignment.columns) == builder.DOCUMENT_POLICY_ALIGNMENT_COLUMNS
    assert document_alignment.loc[0, "support_documents"] == "consulta-6ghz-2026.pdf"
    assert document_alignment["opportunity_score"].between(0, 100).all()
    assert set(document_alignment["coverage_status"]).issubset(set(builder.ALLOWED_COVERAGE_STATUS))
    projects = pd.DataFrame([{
        "project_id": "PMGE-001", "source_document": "pmge.pdf", "pmge_line": "Disponibilidad de espectro",
        "project_name": "Hoja de ruta 6 GHz", "project_description": "Wi-Fi y espectro no licenciado",
        "expected_output": "Hoja de ruta", "timeframe": "2026", "keywords": "6 GHz Wi-Fi uso libre",
    }])
    pmge_alignment = builder.build_pmge_policy_alignment(projects, activities)
    assert list(pmge_alignment.columns) == builder.PMGE_POLICY_ALIGNMENT_COLUMNS
    assert pmge_alignment["alignment_score"].between(0, 100).all()
    assert set(pmge_alignment["alignment_level"]).issubset(set(builder.ALLOWED_ALIGNMENT_LEVEL))
