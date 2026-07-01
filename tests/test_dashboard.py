"""Pruebas de datos y filtros del dashboard de demostración."""
from pathlib import Path
import inspect
import pandas as pd
from streamlit.testing.v1 import AppTest
from app.dashboard import (
    COLOR_ACCENT, COLOR_BLUE, COLOR_GRAY, COLOR_GREEN, COLOR_ORANGE, COLOR_PURPLE,
    DEMO_DATA_DIR, apply_global_filters, build_cross_matrix, build_matrix,
    load_demo_data, parse_list, render_badge, render_metric_card,
    render_relevance_methodology, render_topic_corpus_treemap,
    render_html_heatmap, render_signals_table, short_topic_label, shorten_label,
    render_raw_data_table, render_topic_relevance_bar,
    truncate_label, _render_topic_relevance,
    _build_filtered_signals, _filter_raw_records, _priority_label,
    _render_crosses, _render_raw_data, _render_signals,
    _render_topic_volume, _topic_summary,
)

MINIMUM_COLUMNS = {
    "document_id", "file_name", "source_folder", "tema_estrategico", "linea_pmge",
    "senal_regulatoria", "tecnologias", "bandas_frecuencia", "tipo_insumo_agenda",
    "relevancia_score", "relevancia_label", "prioridad_score",
}

def _records() -> pd.DataFrame:
    return pd.DataFrame([
        {"source_folder": "CRC", "tema_estrategico": "Tema A", "linea_pmge": "Línea A", "tecnologias": '["5G", "NTN"]', "bandas_frecuencia": '["3.5 GHz"]', "tipo_insumo_agenda": "Seguimiento", "relevancia_label": "Alta", "paises_regiones": '["Colombia"]'},
        {"source_folder": "GSMA", "tema_estrategico": "Tema B", "linea_pmge": "Línea B", "tecnologias": '["6G"]', "bandas_frecuencia": '["6 GHz"]', "tipo_insumo_agenda": "Nota técnica", "relevancia_label": "Media", "paises_regiones": '["Francia"]'},
    ])

def test_demo_data_exists_and_records_have_minimum_columns() -> None:
    assert DEMO_DATA_DIR.is_dir()
    records_path = DEMO_DATA_DIR / "dashboard_records.csv"
    assert records_path.is_file()
    assert MINIMUM_COLUMNS.issubset(pd.read_csv(records_path, nrows=1).columns)

def test_load_demo_data_reads_records() -> None:
    assert not load_demo_data()["dashboard_records"].empty

def test_parse_list_supports_json_and_python_literals() -> None:
    assert parse_list('["5G", "6G"]') == ["5G", "6G"]
    assert parse_list("['ITU', 'GSMA']") == ["ITU", "GSMA"]
    assert parse_list("valor inválido") == []

def test_global_filters_combine_scalar_and_list_values() -> None:
    filters = {"source_folder": ["CRC"], "tema_estrategico": [], "linea_pmge": [], "tipo_insumo_agenda": [], "relevancia_label": [], "tecnologias": ["5G"], "bandas_frecuencia": [], "paises_regiones": ["Colombia"]}
    result = apply_global_filters(_records(), filters)
    assert len(result) == 1
    assert result.iloc[0]["source_folder"] == "CRC"

def test_matrices_build_from_filtered_records() -> None:
    filtered = apply_global_filters(_records(), {"relevancia_label": ["Alta"]})
    theme_technology = build_matrix(filtered, "tema_estrategico", "tecnologias")
    band_technology = build_cross_matrix(filtered, "bandas_frecuencia", "tecnologias")
    assert theme_technology.loc["Tema A", "5G"] == 1
    assert band_technology.loc["3.5 GHz", "NTN"] == 1

def test_visual_helpers_escape_and_truncate_content() -> None:
    assert truncate_label("Una etiqueta deliberadamente extensa", 16) == "Una etiqueta de…"
    assert truncate_label("Breve", 16) == "Breve"
    assert shorten_label("Una etiqueta deliberadamente extensa", 16) == "Una etiqueta de…"
    metric = render_metric_card("Tema <activo>", "A&B", "estable", "flat")
    badge = render_badge("Alta <prioridad>", "high")
    assert "Tema &lt;activo&gt;" in metric and "A&amp;B" in metric
    assert 'class="badge badge-high"' in badge and "&lt;prioridad&gt;" in badge

def test_visual_palette_matches_approved_mockup() -> None:
    assert (COLOR_ACCENT, COLOR_BLUE, COLOR_GREEN) == ("#FF4B4B", "#2E5EAA", "#1F9C8A")
    assert (COLOR_ORANGE, COLOR_PURPLE, COLOR_GRAY) == ("#E08E29", "#8A5FBF", "#6b6f7b")

def test_topic_summary_uses_filtered_documents_and_average_relevance() -> None:
    records = pd.DataFrame([
        {"document_id": "1", "tema_estrategico": "Tema A", "relevancia_score": 8},
        {"document_id": "2", "tema_estrategico": "Tema A", "relevancia_score": 6},
        {"document_id": "3", "tema_estrategico": "Tema B", "relevancia_score": 5},
    ])
    summary = _topic_summary(records)
    assert summary.iloc[0]["tema_estrategico"] == "Tema A"
    assert summary.iloc[0]["documentos"] == 2
    assert summary.iloc[0]["relevancia_promedio"] == 7

def test_panorama_charts_use_interactive_plotly_only() -> None:
    source = "\n".join(inspect.getsource(function) for function in (
        _render_topic_volume, render_topic_corpus_treemap, _render_topic_relevance,
    ))
    assert source.count("st.plotly_chart") == 3
    assert "st.pyplot" not in source
    assert "hovertemplate" in source

def test_topic_treemap_uses_controlled_labels_percentages_and_tooltips() -> None:
    assert short_topic_label("Disponibilidad de espectro para IMT") == "Disp. espectro"
    assert short_topic_label("Conectividad satelital, NTN y D2D") == "Satelital/D2D"
    records = pd.DataFrame([
        {"tema_estrategico": "Disponibilidad de espectro para IMT", "tipo_insumo_agenda": "Seguimiento"},
        {"tema_estrategico": "Disponibilidad de espectro para IMT", "tipo_insumo_agenda": "Seguimiento"},
        {"tema_estrategico": "Disponibilidad de espectro para IMT", "tipo_insumo_agenda": "Nueva iniciativa"},
        {"tema_estrategico": "Conectividad satelital, NTN y D2D", "tipo_insumo_agenda": "Nota técnica"},
    ])
    figure = render_topic_corpus_treemap(records)
    assert figure is not None and figure.data[0].type == "treemap"
    assert list(figure.data[0].labels) == ["Disp. espectro", "Satelital/D2D"]
    assert list(figure.data[0].values) == [3, 1]
    assert figure.data[0].customdata[0][0] == "Disponibilidad de espectro para IMT"
    assert figure.data[0].customdata[0][1] == 75.0
    assert "Participación" in figure.data[0].hovertemplate
    assert figure.layout.height == 320

def test_relevance_methodology_handles_data_and_empty_filters() -> None:
    content = render_relevance_methodology(pd.DataFrame([{"document_id": "1"}]))
    assert "Escala 0–10: LLM + línea PMGE + tecnología + banda + fuente + tipo de insumo" in content
    assert "Baja 0–3" in content and "Alta 7–10" in content
    assert render_relevance_methodology(pd.DataFrame()) == ""

def test_filtered_signals_and_html_table_keep_executive_fields() -> None:
    records = pd.DataFrame([{
        "document_id": "1", "senal_regulatoria": "Señal prioritaria", "tema_estrategico": "Tema A",
        "linea_pmge": "Línea A", "tipo_insumo_agenda": "Nueva iniciativa", "relevancia_label": "Alta",
        "source_folder": "UIT", "tecnologias": '["5G"]', "bandas_frecuencia": '["6 GHz"]',
        "evidencia_breve": "Evidencia", "relevancia_score": 8, "actividad_internacional_score": 3,
    }])
    signals = _build_filtered_signals(records)
    assert signals.loc[0, "relevancia_score_promedio"] == 8
    assert signals.loc[0, "actividad_score_promedio"] == 3
    table = render_signals_table(signals)
    assert 'class="signals-table"' in table
    assert "Señal prioritaria" in table and "Nueva iniciativa" in table
    assert "<strong>1 doc</strong>" in table and "Alta" in table

def test_signal_priority_thresholds_and_native_dataframe_removal() -> None:
    assert _priority_label(10) == ("Alta", "high")
    assert _priority_label(8.5) == ("Media-alta", "medium-high")
    assert _priority_label(6.5) == ("Media", "medium")
    assert _priority_label(4.5) == ("Baja-media", "low-medium")
    assert _priority_label(3) == ("Baja", "low")
    assert "st.dataframe" not in inspect.getsource(_render_signals)

def test_html_heatmap_limits_categories_abbreviates_and_marks_zeros() -> None:
    matrix = pd.DataFrame(
        [[8, 0, 1], [2, 3, 0]],
        index=["Disponibilidad de espectro para IMT", "Conectividad satelital, NTN y D2D"],
        columns=["Cullen International", "CRC", "PolicyTracker"],
    )
    component = render_html_heatmap(
        matrix, "Tema estratégico × fuente", "documentos por tema y fuente documental",
        "Fuente", "Tema estratégico", "Mayor intensidad indica más documentos.",
        ("#EAF1FB", "#2E5EAA"), max_rows=1, max_cols=2,
    )
    assert 'class="html-heatmap"' in component
    assert "Disp. espectro" in component and "Cullen" in component
    assert "Satelital/D2D" not in component
    assert "—" in component and "Mayor intensidad indica más documentos." in component

def test_crosses_use_four_html_heatmaps_without_matplotlib() -> None:
    source = inspect.getsource(_render_crosses)
    assert source.count("render_html_heatmap") == 1
    assert "st.pyplot" not in source and "relevancia_label" not in source

def test_topic_relevance_bar_is_compact_sorted_and_uses_zero_to_ten_scale() -> None:
    records = pd.DataFrame([
        {"document_id": "1", "tema_estrategico": "Disponibilidad de espectro para IMT", "relevancia_score": 8},
        {"document_id": "2", "tema_estrategico": "Disponibilidad de espectro para IMT", "relevancia_score": 6},
        {"document_id": "3", "tema_estrategico": "Conectividad satelital, NTN y D2D", "relevancia_score": 9},
    ])
    figure = render_topic_relevance_bar(records)
    assert figure is not None and figure.data[0].type == "bar"
    assert list(figure.data[0].x) == ["Satelital/D2D", "Disp. espectro"]
    assert list(figure.data[0].y) == [9, 7]
    assert list(figure.layout.yaxis.range) == [0, 10]
    assert figure.layout.height == 330
    assert "Documentos" in figure.data[0].hovertemplate

def test_dashboard_renders_visual_structure_without_errors() -> None:
    dashboard_path = Path(__file__).parents[1] / "app" / "dashboard.py"
    app = AppTest.from_file(str(dashboard_path), default_timeout=120).run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == [
        "Panorama estratégico", "Señales emergentes y oportunidades",
        "Cruces analíticos", "Base procesada",
    ]
    assert app.title[0].value == "Vigilancia Tecnológica — PMGE 2026-2030 / Agenda ANE 2027-2028"
    assert [widget.label for widget in app.multiselect] == [
        "Fuente", "Tema estratégico", "Línea PMGE", "Tipo de insumo",
        "Relevancia", "Tecnología", "Banda de frecuencia",
    ]

def test_raw_internal_filters_search_all_requested_fields() -> None:
    records = pd.DataFrame([
        {"file_name": "informe-2026.pdf", "senal_regulatoria": "Señal satelital", "tema_estrategico": "Tema A", "tecnologias": '["NTN"]', "bandas_frecuencia": '["Ka"]', "source_folder": "UIT", "paises_regiones": '["Colombia"]'},
        {"file_name": "otro.pdf", "senal_regulatoria": "Otra señal", "tema_estrategico": "Tema B", "tecnologias": '["5G"]', "bandas_frecuencia": '["700 MHz"]', "source_folder": "CRC", "paises_regiones": '["Francia"]'},
    ])
    assert len(_filter_raw_records(records, "Colombia")) == 1
    assert len(_filter_raw_records(records, "NTN", "Tema A")) == 1
    assert _filter_raw_records(records, "NTN", "Tema B").empty

def test_raw_table_has_only_executive_columns_badges_and_inferred_year() -> None:
    records = pd.DataFrame([{
        "file_name": "consulta-2026.pdf", "source_folder": "UIT",
        "paises_regiones": '["Colombia", "Perú"]',
        "tema_estrategico": "Disponibilidad de espectro para IMT",
        "senal_regulatoria": "Una señal regulatoria", "bandas_frecuencia": '["700 MHz", "3.5 GHz"]',
        "tipo_insumo_agenda": "Nueva iniciativa", "relevancia_score": 8,
    }])
    table = render_raw_data_table(records)
    expected_headers = ["ARCHIVO", "FUENTE", "AÑO", "PAÍS", "TEMA", "SEÑAL", "BANDAS", "TIPO_INSUMO", "REL."]
    assert all(f"<th>{header}</th>" in table for header in expected_headers)
    assert table.count("<th>") == 9
    assert "2026" in table and "Colombia, Perú" in table and "700 MHz / 3.5 GHz" in table
    assert "Disponibilidad y asignación de espectro" in table
    assert 'class="insumo-badge insumo-new"' in table and 'class="rel-hi"' in table
    assert "st.dataframe" not in inspect.getsource(_render_raw_data)
