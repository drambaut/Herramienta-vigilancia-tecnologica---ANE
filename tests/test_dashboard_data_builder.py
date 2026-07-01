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
