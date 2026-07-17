"""Dashboard ejecutivo: modo Supabase publicado o modo demo con ``demo_data``."""
from __future__ import annotations

import ast
import html
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.dashboard_data_builder import build_regulatory_map, build_regulatory_trends
from app.analysis_runs.supabase_repository import SupabaseAnalysisRunRepository
from app.core.settings import load_settings
from app.corpus_snapshots.supabase_repository import SupabaseCorpusSnapshotRepository
from app.dashboard_read.errors import (
    IncompletePublishedRunError,
    NoPublishedAnalysisRunError,
)
from app.dashboard_read.models import DashboardReadModel
from app.dashboard_read.service import DashboardReadService
from app.dashboard_read.supabase_repositories import (
    SupabaseDashboardDocumentReadRepository,
    SupabaseDashboardResultReadRepository,
)
from app.documents.models import SourceType
from app.workflows.manual_processing import ManualDocumentProcessingWorkflowError
from run_manual_processing import build_manual_processing_workflow

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_DATA_DIR = PROJECT_ROOT / "demo_data"
DEMO_FILES = [
    "dashboard_records.csv", "dashboard_signals.csv", "dashboard_temas_counts.csv",
    "dashboard_relevancia_counts.csv", "dashboard_tipo_insumo_counts.csv",
    "dashboard_tecnologias_counts.csv", "dashboard_bandas_counts.csv",
    "dashboard_tema_fuente_matrix.csv", "dashboard_tema_tecnologia_matrix.csv",
    "dashboard_banda_tecnologia_matrix.csv", "dashboard_tema_tipo_insumo_matrix.csv",
    "dashboard_tema_relevancia_matrix.csv", "dashboard_regulatory_map.csv",
    "dashboard_regulatory_trends.csv", "policy_matrix_activities.csv",
    "pmge_projects.csv", "dashboard_document_policy_alignment.csv",
    "dashboard_pmge_policy_alignment.csv",
]
LIST_COLUMNS = {
    "tecnologias", "bandas_frecuencia", "paises_regiones", "organizaciones",
    "actores", "tipo_evento_regulatorio",
}
SCALAR_FILTER_COLUMNS = [
    "source_folder", "tema_estrategico", "linea_pmge",
    "tipo_insumo_agenda", "relevancia_label",
]
LIST_FILTER_COLUMNS = ["tecnologias", "bandas_frecuencia", "paises_regiones"]
COLOR_ACCENT = "#FF4B4B"
COLOR_BLUE = "#2E5EAA"
COLOR_GREEN = "#1F9C8A"
COLOR_ORANGE = "#E08E29"
COLOR_PURPLE = "#8A5FBF"
COLOR_DARK = "#4A4F5A"
COLOR_GRAY = "#6b6f7b"
COLOR_LIGHT_BLUE = "#5B8CCB"
COLOR_LIGHT_GREEN = "#57B8A9"
PALETTE = [COLOR_BLUE, COLOR_GREEN, COLOR_ORANGE, COLOR_PURPLE, COLOR_GRAY]

DASHBOARD_DATA_SOURCE_ENV = "DASHBOARD_DATA_SOURCE"
DASHBOARD_DATA_SOURCE_AUTO = "auto"
DASHBOARD_DATA_SOURCE_DEMO = "demo"
DASHBOARD_DATA_SOURCE_SUPABASE = "supabase"
PUBLIC_UPLOAD_TYPES = ("pdf", "xls", "xlsx")
PUBLIC_UPLOAD_SOURCE_LABELS = {
    SourceType.SURVEILLANCE.value: "Vigilancia",
    SourceType.INSTITUTIONAL_PLAN.value: "PMGE + Agenda Regulatoria",
    SourceType.POLICY_MATRIX.value: "Matriz de politicas",
}

GLOBAL_CSS = f"""
<style>
:root {{ --accent:{COLOR_ACCENT}; --text:#31333F; --muted:{COLOR_GRAY}; --border:#e6e6e6; }}
.stApp {{ background:#fff; color:var(--text); }}
[data-testid="stSidebar"] {{ background:#FFF3E6; border-right:1px solid #F3D7B5; }}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{ color:var(--muted); font-size:.79rem; }}
[data-testid="stSidebar"] h2 {{ font-size:.82rem; text-transform:uppercase; letter-spacing:.045em; margin-bottom:.25rem; }}
.block-container {{ padding-top:1.8rem; padding-bottom:2.5rem; max-width:1500px; }}
h1 {{ font-size:1.65rem !important; line-height:1.22 !important; letter-spacing:-.02em; margin-bottom:.22rem !important; }}
h2 {{ font-size:1.05rem !important; }}
h3 {{ font-size:.9rem !important; margin:.15rem 0 .65rem !important; }}
[data-testid="stCaptionContainer"] {{ color:var(--muted); }}
[data-baseweb="tab-list"] {{ gap:1.25rem; border-bottom:1px solid var(--border); }}
[data-baseweb="tab"] {{ height:2.8rem; padding:0 .1rem; color:var(--muted); font-size:.88rem; font-weight:600; }}
[aria-selected="true"][data-baseweb="tab"] {{ color:var(--accent); }}
[data-testid="stVerticalBlockBorderWrapper"] {{ border-color:var(--border) !important; border-radius:10px !important; background:#fff; box-shadow:0 1px 2px rgba(49,51,63,.025); }}
[data-testid="stDataFrame"] {{ border:1px solid var(--border); border-radius:9px; overflow:hidden; }}
.metric-grid {{ display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:.8rem; margin:.9rem 0 1.35rem; }}
.metric-grid.panorama-grid {{ grid-template-columns:repeat(4,minmax(0,1fr)); }}
.metric-card {{ border:1px solid var(--border); border-radius:10px; background:#fff; padding:.82rem .9rem; min-height:94px; }}
.metric-label {{ color:var(--muted); font-size:.72rem; line-height:1.25; min-height:2.2em; }}
.metric-value {{ color:var(--text); font-size:1.28rem; font-weight:700; line-height:1.18; margin-top:.3rem; overflow-wrap:anywhere; }}
.metric-delta {{ font-size:.7rem; margin-top:.28rem; color:var(--muted); }}
.metric-delta.up {{ color:{COLOR_GREEN}; }} .metric-delta.down {{ color:{COLOR_ACCENT}; }} .metric-delta.warn {{ color:{COLOR_ORANGE}; }}
.section-title {{ display:flex; align-items:center; gap:.55rem; margin:1.15rem 0 .65rem; color:var(--text); font-size:.92rem; font-weight:700; }}
.section-tag {{ color:var(--muted); background:#f5f6f8; border:1px solid var(--border); border-radius:999px; padding:.15rem .48rem; font-size:.65rem; font-weight:600; }}
.custom-card {{ border:1px solid var(--border); border-radius:10px; background:#fff; padding:1rem; }}
.badge {{ display:inline-block; border-radius:999px; padding:.18rem .5rem; font-size:.68rem; font-weight:700; }}
.badge-high,.badge-new {{ color:#157a6b; background:#e7f6f2; }} .badge-medium,.badge-adjust {{ color:#9b6114; background:#fff2df; }}
.badge-low {{ color:#a83737; background:#fdeaea; }} .badge-note {{ color:#69459a; background:#f1eafb; }} .badge-follow {{ color:#244f8f; background:#e8f0fb; }}
.insumo-mini-list {{ width:100%; margin:.35rem 0 .15rem; }}
.insumo-mini-row {{ display:flex; align-items:center; gap:1rem; margin:.72rem 0; min-height:20px; }}
.insumo-mini-label {{ width:190px; min-width:190px; color:#31333F; font-size:.78rem; font-weight:600; line-height:1.15; }}
.insumo-mini-scale {{ flex:1; min-width:80px; }}
.insumo-mini-track {{ display:flex; height:16px; overflow:hidden; border-radius:4px; background:#f0f2f6; box-shadow:inset 0 0 0 1px rgba(49,51,63,.04); }}
.insumo-mini-total {{ width:48px; min-width:48px; color:var(--muted); font-size:.68rem; font-weight:600; white-space:nowrap; }}
.insumo-mini-segment {{ height:100%; min-width:0; transition:filter .15s ease; }}
.insumo-mini-segment:hover {{ filter:brightness(.9); }}
.insumo-mini-note {{ margin:.1rem 0 .85rem; color:var(--muted); font-size:.7rem; line-height:1.35; }}
.insumo-mini-legend {{ display:flex; flex-wrap:wrap; gap:.55rem 1rem; margin-top:1rem; padding-top:.7rem; border-top:1px solid var(--border); color:var(--muted); font-size:.7rem; }}
.insumo-mini-legend-item {{ display:inline-flex; align-items:center; gap:.35rem; }}
.insumo-mini-dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}
.relevance-method {{ display:flex; align-items:center; align-content:center; flex-wrap:wrap; gap:.5rem .75rem; min-height:96px; padding:.2rem .15rem; color:#31333F; box-sizing:border-box; }}
.relevance-method-title {{ width:100%; font-size:.78rem; font-weight:700; line-height:1.2; }}
.relevance-method-line {{ width:100%; color:var(--muted); font-size:.7rem; line-height:1.35; overflow-wrap:anywhere; }}
.relevance-scale {{ display:flex; flex-wrap:wrap; gap:.35rem; margin-left:0; }}
.relevance-level {{ border-radius:999px; padding:.2rem .48rem; font-size:.65rem; font-weight:700; white-space:nowrap; }}
.relevance-low {{ background:#f1f2f4; color:#656a73; }} .relevance-medium {{ background:#fff2df; color:#9b6114; }} .relevance-high {{ background:#e7f6f2; color:#157a6b; }}
.bubble-card {{ background:#fff; min-height:520px; }}
.method-card {{ background:#fff; border:1px solid var(--border); border-radius:10px; padding:1rem 1.1rem; min-height:520px; box-sizing:border-box; }}
.method-card h4 {{ margin:0 0 .15rem; font-size:.9rem; color:#31333F; }}
.method-card .method-sub {{ color:var(--muted); font-size:.72rem; margin-bottom:1.4rem; }}
.method-formula {{ background:#f7f8fa; border:1px solid var(--border); border-radius:8px; padding:.75rem; color:#31333F; font-size:.8rem; font-weight:700; line-height:1.45; }}
.method-priorities {{ display:flex; flex-direction:column; gap:.8rem; margin-top:1.25rem; }}
.method-priority {{ display:flex; align-items:flex-start; gap:.55rem; color:#4A4F5A; font-size:.73rem; line-height:1.35; }}
.method-dot {{ width:9px; height:9px; min-width:9px; border-radius:50%; margin-top:.16rem; }}
.signals-card {{ border:1px solid var(--border); border-radius:10px; background:#fff; padding:.25rem 1rem .5rem; overflow-x:auto; }}
.signals-table {{ width:100%; border-collapse:collapse; font-size:.76rem; }}
.signals-table th {{ padding:.65rem .55rem; color:var(--muted); font-size:.65rem; letter-spacing:.035em; text-align:left; border-bottom:1px solid var(--border); white-space:nowrap; }}
.signals-table td {{ padding:.72rem .55rem; color:#31333F; border-bottom:1px solid #f0f1f3; vertical-align:top; line-height:1.35; }}
.signals-table tr:last-child td {{ border-bottom:0; }}
.signal-badge,.signal-topic-tag {{ display:inline-block; border-radius:999px; padding:.2rem .48rem; font-size:.65rem; font-weight:700; line-height:1.25; }}
.signal-topic-tag {{ background:#f0f2f6; color:#525762; font-weight:600; }}
.signal-new {{ background:#E6F4EA; color:#1F9C5C; }} .signal-adjust {{ background:#FDEFE0; color:#E08E29; }}
.signal-note {{ background:#EAE3F7; color:#8A5FBF; }} .signal-follow {{ background:#E7EEFB; color:#2E5EAA; }} .signal-low {{ background:#EDEFF3; color:#6b6f7b; }}
.priority-text {{ font-size:.7rem; font-weight:800; white-space:nowrap; }}
.priority-high {{ color:#D64545; }} .priority-medium-high,.priority-medium {{ color:#E08E29; }} .priority-low-medium,.priority-low {{ color:#6b6f7b; }}
.analytics-card {{ background:#fff; border:1px solid var(--border); border-radius:10px; padding:.9rem 1rem .8rem; min-height:445px; box-sizing:border-box; margin-bottom:1rem; }}
.analytics-card h4 {{ margin:0 0 .12rem; color:#31333F; font-size:.88rem; }}
.analytics-subtitle {{ color:var(--muted); font-size:.7rem; margin-bottom:.7rem; }}
.heatmap-scroll {{ width:100%; overflow-x:auto; padding-bottom:.2rem; }}
.html-heatmap {{ width:100%; border-collapse:separate; border-spacing:3px; table-layout:fixed; font-size:.66rem; }}
.html-heatmap th {{ color:var(--muted); font-size:.61rem; font-weight:700; line-height:1.15; padding:.2rem .12rem; text-align:center; overflow-wrap:anywhere; }}
.html-heatmap th:first-child {{ width:105px; text-align:left; }}
.html-heatmap .row-label {{ color:#444954; font-size:.65rem; font-weight:650; text-align:left; padding-right:.3rem; }}
.html-heatmap td {{ height:34px; border-radius:5px; text-align:center; font-weight:750; }}
.heatmap-axis-x {{ color:var(--muted); font-size:.62rem; text-align:center; margin-bottom:.2rem; font-weight:650; }}
.heatmap-note {{ color:var(--muted); font-size:.66rem; line-height:1.3; margin-top:.65rem; padding-top:.55rem; border-top:1px solid #f0f1f3; }}
.heatmap-note b {{ color:#525762; }}
.raw-section-title {{ display:flex; align-items:center; gap:.55rem; margin:.2rem 0 .7rem; }}
.raw-section-title h3 {{ margin:0 !important; font-size:1rem !important; }}
.raw-section-pill {{ border:1px solid var(--border); border-radius:999px; background:#f5f6f8; color:var(--muted); padding:.16rem .48rem; font-size:.64rem; font-weight:700; letter-spacing:.025em; }}
.schema-note {{ background:#fafbfc; border:1px solid var(--border); border-radius:6px; color:var(--muted); padding:.55rem .7rem; margin-bottom:.75rem; font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace; font-size:.68rem; overflow-wrap:anywhere; }}
.raw-search-row {{ margin:.2rem 0 .45rem; }}
.docs-wrap {{ width:100%; max-height:430px; overflow:auto; border:1px solid var(--border); border-radius:10px; background:#fff; }}
.docs-table {{ width:100%; min-width:1120px; border-collapse:collapse; font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace; font-size:.68rem; }}
.docs-table th {{ position:sticky; top:0; z-index:2; background:#f7f8fa; color:#555b66; padding:.6rem .55rem; border-bottom:1px solid var(--border); text-align:left; font-family:"Source Sans Pro",sans-serif; font-size:.62rem; letter-spacing:.035em; white-space:nowrap; }}
.docs-table td {{ color:#3f444d; padding:.58rem .55rem; border-bottom:1px solid #f0f1f3; vertical-align:top; line-height:1.35; }}
.docs-table tbody tr:hover td {{ background:#fbfbfc; }}
.docs-table tbody tr:last-child td {{ border-bottom:0; }}
.source-pill,.insumo-badge {{ display:inline-block; border-radius:999px; padding:.18rem .42rem; font-family:"Source Sans Pro",sans-serif; font-size:.63rem; font-weight:700; white-space:nowrap; }}
.source-pill {{ background:#EDEFF3; color:#59606b; }}
.insumo-new {{ background:#E6F4EA; color:#1F9C5C; }} .insumo-adjust {{ background:#FDEFE0; color:#E08E29; }}
.insumo-note {{ background:#EAE3F7; color:#8A5FBF; }} .insumo-follow {{ background:#E7EEFB; color:#2E5EAA; }} .insumo-low {{ background:#EDEFF3; color:#6b6f7b; }}
.rel-hi,.rel-mid,.rel-low {{ font-weight:800; font-family:"Source Sans Pro",sans-serif; }}
.rel-hi {{ color:#1F9C5C; }} .rel-mid {{ color:#E08E29; }} .rel-low {{ color:#6b6f7b; }}
.raw-footnote {{ color:var(--muted); font-size:.66rem; margin-top:.5rem; }}
.raw-empty {{ border:1px solid var(--border); border-radius:10px; background:#fff; color:var(--muted); padding:1rem; font-size:.78rem; }}
.reg-filterbar {{ margin:.45rem 0 .85rem; padding:.72rem .85rem .15rem; border:1px solid var(--border); border-radius:10px; background:#fafbfc; }}
.reg-table-wrap {{ width:100%; overflow:auto; border:1px solid var(--border); border-radius:10px; background:#fff; }}
.reg-table {{ width:100%; min-width:1080px; border-collapse:collapse; font-size:.73rem; }}
.reg-table th {{ padding:.62rem .55rem; color:var(--muted); font-size:.62rem; letter-spacing:.04em; text-align:left; border-bottom:1px solid var(--border); white-space:nowrap; }}
.reg-table td {{ padding:.68rem .55rem; color:#31333F; border-bottom:1px solid #f0f1f3; vertical-align:top; line-height:1.35; }}
.reg-table tr:last-child td {{ border-bottom:0; }}
.two-line {{ display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; max-width:310px; }}
.topic-badge {{ display:inline-block; border-radius:999px; padding:.2rem .48rem; background:#f0f2f6; color:#525762; font-size:.64rem; font-weight:700; }}
.trend-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; margin-top:.7rem; }}
.trend-card {{ border:1px solid var(--border); border-radius:10px; background:#fff; padding:1rem 1.05rem; min-width:0; }}
.trend-card h4 {{ margin:.45rem 0 .75rem; color:#31333F; font-size:.96rem; line-height:1.25; }}
.trend-topic {{ margin-bottom:.35rem; }}
.trend-field {{ margin:.62rem 0; color:#4A4F5A; font-size:.75rem; line-height:1.42; }}
.trend-field b {{ display:block; margin-bottom:.12rem; color:#31333F; font-size:.7rem; }}
.trend-footer {{ display:flex; flex-wrap:wrap; gap:.4rem; margin-top:.8rem; padding-top:.7rem; border-top:1px solid #f0f1f3; }}
.doc-pill {{ display:inline-block; max-width:190px; overflow:hidden; text-overflow:ellipsis; vertical-align:middle; border-radius:999px; background:#EDEFF3; color:#59606b; padding:.16rem .45rem; margin:.08rem .12rem .08rem 0; font-size:.62rem; font-weight:700; white-space:nowrap; }}
.align-source-note {{ display:inline-block; margin:.15rem 0 1rem; border-radius:999px; background:#f5f6f8; color:var(--muted); padding:.28rem .7rem; font-size:.72rem; font-weight:700; }}
.align-filterbar {{ margin:.3rem 0 1rem; padding:.72rem .85rem .1rem; border:1px solid var(--border); border-radius:10px; background:#fafbfc; }}
.align-table-wrap {{ width:100%; overflow:auto; border:1px solid var(--border); border-radius:10px; background:#fff; }}
.align-table {{ width:100%; min-width:1180px; border-collapse:collapse; font-size:.72rem; }}
.align-table th {{ padding:.62rem .55rem; color:var(--muted); font-size:.61rem; letter-spacing:.04em; text-align:left; border-bottom:1px solid var(--border); white-space:nowrap; }}
.align-table td {{ padding:.68rem .55rem; color:#31333F; border-bottom:1px solid #f0f1f3; vertical-align:top; line-height:1.35; }}
.align-table tr:last-child td {{ border-bottom:0; }}
.align-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; margin-top:.7rem; }}
.align-card {{ border:1px solid var(--border); border-radius:10px; background:#fff; padding:1rem 1.05rem; min-width:0; }}
.align-card h4 {{ margin:.4rem 0 .65rem; color:#31333F; font-size:.9rem; line-height:1.25; }}
.align-field {{ margin:.5rem 0; color:#4A4F5A; font-size:.74rem; line-height:1.38; }}
.align-field b {{ display:block; color:#31333F; font-size:.68rem; margin-bottom:.12rem; }}
.weight-row {{ display:flex; align-items:center; gap:.7rem; margin:.52rem 0; }}
.weight-row .w-lbl {{ width:210px; min-width:210px; font-size:.72rem; color:#31333F; }}
.weight-row .w-bar {{ flex:1; height:10px; background:#f1f2f4; border-radius:999px; overflow:hidden; }}
.weight-row .w-fill {{ height:100%; border-radius:999px; background:{COLOR_ACCENT}; }}
.weight-row .w-pct {{ width:36px; text-align:right; font-size:.72rem; font-weight:800; }}
.hm-status-alta {{ background:#1F9C5C; color:#fff; }} .hm-status-parcial {{ background:#E08E29; color:#fff; }} .hm-status-brecha {{ background:#D64545; color:#fff; }} .hm-status-se {{ background:#EDEFF3; color:#8a8d97; }}
@media (max-width:700px) {{ .insumo-mini-row {{ align-items:flex-start; display:grid; grid-template-columns:1fr 42px; gap:.35rem .5rem; }} .insumo-mini-label {{ width:100%; min-width:0; grid-column:1 / -1; }} .insumo-mini-scale {{ width:100%; }} .insumo-mini-total {{ width:42px; min-width:42px; }} }}
div[data-testid="stBarChart"], div[data-testid="stVegaLiteChart"] {{ max-height:390px; }}
@media (max-width:1200px) {{ .metric-grid {{ grid-template-columns:repeat(3,minmax(0,1fr)); }} .metric-grid.panorama-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
@media (max-width:700px) {{ .metric-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .trend-grid,.align-grid {{ grid-template-columns:1fr; }} .block-container {{ padding-top:1rem; }} }}
</style>
"""


def truncate_label(text: Any, max_len: int = 32) -> str:
    """Acorta una etiqueta para presentación sin modificar el valor original."""
    value = str(text or "").strip()
    return value if len(value) <= max_len else value[: max_len - 1].rstrip() + "…"


def shorten_label(label: str, max_len: int = 36) -> str:
    """Alias semántico para abreviar etiquetas de ejes interactivos."""
    return truncate_label(label, max_len)


def short_topic_label(topic: str) -> str:
    """Devuelve la abreviación ejecutiva acordada para cada tema controlado."""
    labels = {
        "Disponibilidad de espectro para IMT": "Disp. espectro",
        "Conectividad satelital, NTN y D2D": "Satelital/D2D",
        "Bandas medias y altas para servicios móviles": "Bandas altas IMT",
        "Spectrum sharing y mecanismos flexibles": "Sharing/flexible",
        "6 GHz, Wi-Fi e IMT": "Wi-Fi/6GHz",
        "Redes privadas y verticales industriales": "Redes privadas",
        "Armonización y gestión internacional": "Gestión intl.",
        "Necesidades transversales y capacidades institucionales": "Transversales",
        "Otros temas de seguimiento": "Otros",
    }
    return labels.get(str(topic), shorten_label(str(topic), 28))


def render_relevance_methodology(records: pd.DataFrame) -> str:
    """Muestra una síntesis ejecutiva y compacta del cálculo de relevancia."""
    with st.container(border=True):
        if records.empty:
            st.info("No hay registros para calcular relevancia con los filtros actuales.")
            return ""
        content = (
            '<div class="relevance-method">'
            '<div class="relevance-method-title">Cómo se calcula la relevancia</div>'
            '<div class="relevance-method-line">Escala 0–10: LLM + línea PMGE + tecnología + banda + fuente + tipo de insumo</div>'
            '<div class="relevance-scale">'
            '<div class="relevance-level relevance-low">Baja 0–3</div>'
            '<div class="relevance-level relevance-medium">Media 4–6</div>'
            '<div class="relevance-level relevance-high">Alta 7–10</div>'
            '</div></div>'
        )
        st.markdown(content, unsafe_allow_html=True)
        return content


def render_metric_card(label: Any, value: Any, delta: Any = None, delta_type: str = "flat") -> str:
    """Devuelve una tarjeta KPI segura y controlada por CSS."""
    delta_html = ""
    if delta is not None:
        delta_html = f'<div class="metric-delta {html.escape(delta_type)}">{html.escape(str(delta))}</div>'
    return (
        '<div class="metric-card">'
        f'<div class="metric-label">{html.escape(str(label))}</div>'
        f'<div class="metric-value" title="{html.escape(str(value))}">{html.escape(str(value))}</div>'
        f'{delta_html}</div>'
    )


def render_section_title(title: Any, tag: Any = None) -> None:
    tag_html = f'<span class="section-tag">{html.escape(str(tag))}</span>' if tag else ""
    st.markdown(f'<div class="section-title">{html.escape(str(title))}{tag_html}</div>', unsafe_allow_html=True)


def dashboard_data_source(environ: dict[str, str] | None = None) -> str:
    source_env = environ or os.environ
    source = source_env.get(DASHBOARD_DATA_SOURCE_ENV, DASHBOARD_DATA_SOURCE_AUTO)
    normalized = source.strip().lower() or DASHBOARD_DATA_SOURCE_AUTO
    if normalized == DASHBOARD_DATA_SOURCE_AUTO:
        settings = load_settings(environ=source_env)
        if settings.supabase_url and settings.supabase_key:
            return DASHBOARD_DATA_SOURCE_SUPABASE
        return DASHBOARD_DATA_SOURCE_DEMO
    if normalized not in {DASHBOARD_DATA_SOURCE_DEMO, DASHBOARD_DATA_SOURCE_SUPABASE}:
        return DASHBOARD_DATA_SOURCE_DEMO
    return normalized


def build_supabase_dashboard_service() -> DashboardReadService:
    settings = load_settings()
    return DashboardReadService(
        analysis_runs=SupabaseAnalysisRunRepository(settings=settings),
        snapshots=SupabaseCorpusSnapshotRepository(settings=settings),
        documents=SupabaseDashboardDocumentReadRepository(settings=settings),
        results=SupabaseDashboardResultReadRepository(settings=settings),
    )


def load_published_dashboard_model(
    service: DashboardReadService | None = None,
) -> DashboardReadModel:
    return (service or build_supabase_dashboard_service()).get_published_dashboard()


def upload_content_type(file_name: str) -> str:
    extension = Path(file_name).suffix.lower()
    if extension == ".pdf":
        return "application/pdf"
    if extension == ".xls":
        return "application/vnd.ms-excel"
    if extension == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "application/octet-stream"


def public_upload_metadata(provider: str, *, smoke: bool) -> dict[str, str]:
    normalized_provider = provider.strip() or "dashboard"
    return {
        "origin": "dashboard_upload",
        "provider": normalized_provider,
        "smoke": "true" if smoke else "false",
    }


def render_supabase_upload_panel(
    workflow_factory=build_manual_processing_workflow,
) -> None:
    with st.sidebar.expander("Cargar documento", expanded=False):
        st.caption(
            "Carga publica temporal. Procesa PDF/Excel en Supabase y Gemini; "
            "para verlo en el dashboard hay que publicar un nuevo analisis transversal."
        )
        uploaded_file = st.file_uploader(
            "PDF o Excel",
            type=list(PUBLIC_UPLOAD_TYPES),
            accept_multiple_files=False,
            key="supabase_public_upload",
        )
        source_type_value = st.selectbox(
            "Tipo de fuente",
            options=list(PUBLIC_UPLOAD_SOURCE_LABELS),
            format_func=lambda value: PUBLIC_UPLOAD_SOURCE_LABELS[value],
            key="supabase_public_upload_source_type",
        )
        provider = st.text_input(
            "Proveedor / origen",
            value="dashboard",
            key="supabase_public_upload_provider",
        )
        smoke = st.checkbox(
            "Modo smoke tecnico",
            value=True,
            help="Extrae una muestra pequena para validar carga y procesamiento.",
            key="supabase_public_upload_smoke",
        )
        if st.button(
            "Subir y procesar",
            disabled=uploaded_file is None,
            key="supabase_public_upload_submit",
        ):
            if uploaded_file is None:
                st.warning("Selecciona un archivo PDF, XLS o XLSX.")
                return
            file_name = uploaded_file.name
            extension = Path(file_name).suffix.lower().lstrip(".")
            if extension not in PUBLIC_UPLOAD_TYPES:
                st.error("Formato no soportado. Usa PDF, XLS o XLSX.")
                return
            metadata = public_upload_metadata(provider, smoke=smoke)
            try:
                with st.spinner("Procesando documento..."):
                    result = workflow_factory().run(
                        file_name=file_name,
                        file_bytes=uploaded_file.getvalue(),
                        source_type=SourceType(source_type_value),
                        metadata=metadata,
                        content_type=upload_content_type(file_name),
                    )
            except ManualDocumentProcessingWorkflowError as exc:
                st.error(f"No se pudo procesar el documento en {exc.stage}.")
                st.caption(str(exc.original_error))
                return
            except Exception as exc:
                st.error("No se pudo procesar el documento.")
                st.caption(str(exc))
                return
            st.success(f"Documento procesado: {result.document.file_name}")
            st.caption(f"document_id={result.document.id}")
            st.info(
                "Para que aparezca en el dashboard publicado, ejecuta un nuevo "
                "analisis transversal y publica la version resultante."
            )


def render_supabase_dashboard(model: DashboardReadModel) -> None:
    summary = model.summary
    st.sidebar.markdown(
        render_metric_card("Publicacion vigente", summary.published_at or "S/F"),
        unsafe_allow_html=True,
    )
    st.markdown("## Panorama estrategico publicado")
    st.caption(
        "Datos leidos desde DashboardReadService; no se recalculan scores, no se llama Gemini y no se leen archivos originales."
    )
    metrics = [
        ("Documentos", summary.document_count),
        ("Hallazgos", summary.finding_count),
        ("Evidencias", summary.evidence_count),
        ("Temas", model.strategic_overview.theme_count),
        ("Tendencias", model.strategic_overview.trend_count),
        ("Senales", model.strategic_overview.emerging_signal_count),
    ]
    st.markdown(
        '<div class="metric-grid">'
        + "".join(render_metric_card(label, value) for label, value in metrics)
        + "</div>",
        unsafe_allow_html=True,
    )
    tabs = st.tabs(
        [
            "Temas",
            "Inteligencia regulatoria",
            "Oportunidades",
            "Alineacion PMGE",
            "Documentos",
        ]
    )
    with tabs[0]:
        _render_read_model_table(
            [
                {
                    "Tema": item.name,
                    "Alcance": item.scope,
                    "Confianza": item.confidence,
                    "Hallazgos": len(item.finding_ids),
                }
                for item in model.themes
            ],
            "No hay temas publicados.",
        )
    with tabs[1]:
        _render_read_model_table(
            [
                {
                    "Situacion internacional": item.international_situation,
                    "Relacion agenda": item.relationship_type,
                    "Implicaciones ANE": item.implications_for_ane,
                    "Confianza": item.confidence,
                }
                for item in model.regulatory_intelligence
            ],
            "No hay inteligencia regulatoria publicada.",
        )
    with tabs[2]:
        _render_read_model_table(
            [
                {
                    "Tema": item.theme_id,
                    "Score": item.opportunity_score,
                    "Nivel": item.level,
                    "Accion sugerida": item.suggested_action,
                }
                for item in model.opportunities
            ],
            "No hay oportunidades publicadas.",
        )
    with tabs[3]:
        _render_read_model_table(
            [
                {
                    "Tema": item.theme_id,
                    "Score": item.alignment_score,
                    "Nivel": item.level,
                    "Tipo": item.alignment_type,
                }
                for item in model.pmge_alignment
            ],
            "No hay alineacion PMGE publicada.",
        )
    with tabs[4]:
        _render_read_model_table(
            [
                {
                    "Archivo": item.file_name,
                    "Tipo": item.file_type,
                    "Fuente": item.source_type,
                    "Estado": item.status,
                }
                for item in model.documents
            ],
            "No hay documentos publicados.",
        )


def _render_read_model_table(rows: list[dict[str, Any]], empty_message: str) -> None:
    if not rows:
        st.info(empty_message)
        return
    st.table(pd.DataFrame(rows))


def render_no_published_dashboard_state(message: str | None = None) -> None:
    st.info(
        message
        or "Todavia no hay una publicacion vigente. Procesa documentos y publica un analisis transversal para activar el dashboard Supabase."
    )


def render_card_start() -> None:
    st.markdown('<div class="custom-card">', unsafe_allow_html=True)


def render_card_end() -> None:
    st.markdown('</div>', unsafe_allow_html=True)


def render_badge(text: Any, kind: str) -> str:
    safe_kind = "".join(char for char in str(kind).casefold() if char.isalnum() or char == "-")
    return f'<span class="badge badge-{safe_kind}">{html.escape(str(text))}</span>'


def render_doc_pills(value: Any, max_docs: int = 3) -> str:
    docs = [item.strip() for item in re.split(r"\s*\|\s*|,\s*", str(value or "")) if item.strip()]
    if not docs:
        return "—"
    shown = "".join(
        f'<span class="doc-pill" title="{html.escape(doc, quote=True)}">{html.escape(shorten_label(doc, 34))}</span>'
        for doc in docs[:max_docs]
    )
    extra = len(docs) - max_docs
    return shown + (f'<span class="doc-pill">+{extra} docs</span>' if extra > 0 else "")


def render_html_table(dataframe: pd.DataFrame, columns: list[tuple[str, str]], empty_text: str = "No hay datos para los filtros actuales.") -> str:
    if dataframe.empty:
        content = f'<div class="raw-empty">{html.escape(empty_text)}</div>'
        st.markdown(content, unsafe_allow_html=True)
        return content
    headers = "".join(f"<th>{html.escape(label)}</th>" for _, label in columns)
    rows: list[str] = []
    for _, row in dataframe.iterrows():
        cells: list[str] = []
        for column, _ in columns:
            value = row.get(column, "—")
            if column in {"support_documents"}:
                rendered = render_doc_pills(value)
            elif column in {"coverage_status", "alignment_level", "recommendation", "suggested_action", "score_label"}:
                rendered = render_badge(value or "—", _badge_kind(value))
            elif column in {"opportunity_score", "alignment_score"}:
                rendered = f"<strong>{float(pd.to_numeric(pd.Series([value]), errors='coerce').fillna(0).iloc[0]):.1f}</strong>"
            else:
                rendered = html.escape(shorten_label(str(value or "—"), 140))
            cells.append(f"<td>{rendered}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    content = f'<div class="align-table-wrap"><table class="align-table"><thead><tr>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    st.markdown(content, unsafe_allow_html=True)
    return content


def _badge_kind(value: Any) -> str:
    text = str(value or "").casefold()
    if any(term in text for term in ("alta", "existente")):
        return "high"
    if any(term in text for term in ("parcial", "media", "ajuste")):
        return "medium"
    if any(term in text for term in ("brecha", "débil", "debil", "baja")):
        return "low"
    if "nota" in text:
        return "note"
    return "follow"


def short_label(value: Any, max_len: int = 28) -> str:
    return shorten_label(str(value or ""), max_len)


def parse_list(value: Any) -> list[str]:
    """Interpreta listas JSON o Python sin ejecutar código."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, (list, tuple, set)):
        parsed = list(value)
    else:
        raw = str(value).strip()
        if not raw:
            return []
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(raw)
                break
            except (json.JSONDecodeError, ValueError, SyntaxError, TypeError):
                parsed = None
        if parsed is None:
            return []
    if isinstance(parsed, str):
        parsed = [parsed]
    return [str(item).strip() for item in parsed if str(item).strip()] if isinstance(parsed, (list, tuple, set)) else []


@st.cache_data(show_spinner=False)
def load_demo_data() -> dict[str, pd.DataFrame]:
    """Carga todos los CSV de demo; los faltantes se representan como tablas vacías."""
    data: dict[str, pd.DataFrame] = {}
    if not DEMO_DATA_DIR.is_dir():
        st.warning(f"No se encontró la carpeta de datos de demostración: {DEMO_DATA_DIR}")
        return {Path(name).stem: pd.DataFrame() for name in DEMO_FILES}
    missing: list[str] = []
    for filename in DEMO_FILES:
        path = DEMO_DATA_DIR / filename
        key = path.stem
        if not path.is_file():
            missing.append(filename)
            data[key] = pd.DataFrame()
            continue
        try:
            data[key] = pd.read_csv(path, encoding="utf-8-sig")
        except (OSError, UnicodeError, pd.errors.ParserError) as exc:
            missing.append(filename)
            data[key] = pd.DataFrame()
            st.warning(f"No fue posible leer {filename}: {exc}")
    if missing:
        st.warning("Faltan archivos de demostración: " + ", ".join(missing))
    return data


def explode_list_column(dataframe: pd.DataFrame, column: str) -> pd.DataFrame:
    """Expande una columna con listas serializadas conservando las demás columnas."""
    if column not in dataframe.columns:
        return dataframe.iloc[0:0].copy()
    result = dataframe.copy()
    result[column] = result[column].apply(parse_list)
    return result.explode(column).dropna(subset=[column]).reset_index(drop=True)


def count_list_values(dataframe: pd.DataFrame, column: str) -> pd.Series:
    exploded = explode_list_column(dataframe, column)
    if exploded.empty:
        return pd.Series(dtype="int64", name="count")
    return exploded[column].astype(str).loc[lambda s: s.str.len() > 0].value_counts()


def build_count_df(dataframe: pd.DataFrame, column: str) -> pd.DataFrame:
    """Construye conteos para columnas escalares o de listas."""
    if column not in dataframe.columns:
        return pd.DataFrame(columns=[column, "count"])
    counts = count_list_values(dataframe, column) if column in LIST_COLUMNS else dataframe[column].dropna().astype(str).loc[lambda s: s.str.len() > 0].value_counts()
    return counts.rename_axis(column).reset_index(name="count")


def build_matrix(dataframe: pd.DataFrame, row_col: str, list_col_or_col: str) -> pd.DataFrame:
    """Cruza una variable escalar con otra escalar o serializada como lista."""
    if not {row_col, list_col_or_col}.issubset(dataframe.columns):
        return pd.DataFrame()
    pairs = explode_list_column(dataframe[[row_col, list_col_or_col]], list_col_or_col) if list_col_or_col in LIST_COLUMNS else dataframe[[row_col, list_col_or_col]].copy()
    pairs = pairs.dropna().reset_index(drop=True)
    return pd.crosstab(pairs[row_col], pairs[list_col_or_col]) if not pairs.empty else pd.DataFrame()


def build_cross_matrix(dataframe: pd.DataFrame, row_col: str, col_col: str) -> pd.DataFrame:
    """Cruza columnas escalares o listas, expandiendo ambas cuando corresponde."""
    if not {row_col, col_col}.issubset(dataframe.columns):
        return pd.DataFrame()
    pairs = dataframe[[row_col, col_col]].copy()
    if row_col in LIST_COLUMNS:
        pairs = explode_list_column(pairs, row_col)
    if col_col in LIST_COLUMNS:
        pairs = explode_list_column(pairs, col_col)
    pairs = pairs.dropna().reset_index(drop=True)
    return pd.crosstab(pairs[row_col], pairs[col_col]) if not pairs.empty else pd.DataFrame()


def _matches_list(value: Any, selected: list[str]) -> bool:
    available = {item.casefold() for item in parse_list(value)}
    return bool(available.intersection(item.casefold() for item in selected))


def apply_global_filters(records_df: pd.DataFrame, filters: dict[str, list[str]]) -> pd.DataFrame:
    """Aplica en conjunto los filtros escalares y de campos multivalor."""
    filtered = records_df.copy()
    for column in SCALAR_FILTER_COLUMNS:
        selected = filters.get(column, [])
        if selected and column in filtered.columns:
            choices = {item.casefold() for item in selected}
            filtered = filtered[filtered[column].fillna("").astype(str).str.strip().str.casefold().isin(choices)]
    for column in LIST_FILTER_COLUMNS:
        selected = filters.get(column, [])
        if selected and column in filtered.columns:
            filtered = filtered[filtered[column].apply(lambda value: _matches_list(value, selected))]
    return filtered.reset_index(drop=True)


def _options(records: pd.DataFrame, column: str, is_list: bool = False) -> list[str]:
    if column not in records.columns:
        return []
    if is_list:
        values = {item for value in records[column] for item in parse_list(value)}
    else:
        values = {str(value).strip() for value in records[column].dropna() if str(value).strip()}
    return sorted(values, key=str.casefold)


def _render_filters(records: pd.DataFrame) -> dict[str, list[str]]:
    st.sidebar.markdown("### Filtros")
    st.sidebar.caption("Los filtros se aplican a todas las vistas analíticas.")
    labels = {
        "source_folder": "Fuente", "tema_estrategico": "Tema estratégico",
        "linea_pmge": "Línea PMGE", "tecnologias": "Tecnología",
        "bandas_frecuencia": "Banda de frecuencia", "tipo_insumo_agenda": "Tipo de insumo",
        "relevancia_label": "Relevancia", "paises_regiones": "País o región",
    }
    filters: dict[str, list[str]] = {}
    filter_columns = [
        "source_folder", "tema_estrategico", "linea_pmge", "tipo_insumo_agenda",
        "relevancia_label", "tecnologias", "bandas_frecuencia",
    ]
    for column in filter_columns:
        options = _options(records, column, column in LIST_COLUMNS)
        filters[column] = st.sidebar.multiselect(labels[column], options)
    return filters


def _bar_chart(counts: pd.DataFrame, column: str, title: str, limit: int = 10) -> None:
    with st.container(border=True):
        st.markdown(f"### {title}")
        if counts.empty:
            st.info("No hay datos para los filtros seleccionados.")
            return
        chart = counts.head(limit).copy()
        chart[column] = chart[column].map(truncate_label)
        st.bar_chart(chart.set_index(column)["count"], horizontal=True, color=COLOR_BLUE, height=300)


def _dominant(records: pd.DataFrame, column: str) -> str:
    counts = build_count_df(records, column)
    return str(counts.iloc[0][column]) if not counts.empty else "Sin datos"


def _topic_summary(records: pd.DataFrame, limit: int = 7) -> pd.DataFrame:
    """Resume volumen y relevancia por tema sobre el subconjunto filtrado."""
    columns = ["tema_estrategico", "documentos", "relevancia_promedio"]
    if records.empty or "tema_estrategico" not in records.columns:
        return pd.DataFrame(columns=columns)
    working = records.copy()
    working["relevancia_score"] = pd.to_numeric(
        working.get("relevancia_score", pd.Series(index=working.index, dtype=float)),
        errors="coerce",
    )
    document_column = "document_id" if "document_id" in working.columns else "tema_estrategico"
    summary = working.groupby("tema_estrategico", dropna=False).agg(
        documentos=(document_column, "nunique"),
        relevancia_promedio=("relevancia_score", "mean"),
    ).reset_index()
    return summary.sort_values(["documentos", "relevancia_promedio"], ascending=False).head(limit)


def _render_topic_volume(records: pd.DataFrame) -> None:
    counts = build_count_df(records, "tema_estrategico").head(8)
    with st.container(border=True):
        st.markdown("### Volumen documental por tema")
        st.caption("n° de documentos asociados a cada tema, según filtros aplicados")
        if counts.empty:
            st.info("No hay temas para los filtros seleccionados.")
            return
        colors = [COLOR_BLUE, COLOR_GREEN, COLOR_ORANGE, COLOR_PURPLE, COLOR_DARK, COLOR_GRAY, COLOR_LIGHT_BLUE, COLOR_LIGHT_GREEN]
        full_topics = counts["tema_estrategico"].astype(str).tolist()
        axis_topics = [shorten_label(topic) for topic in full_topics]
        fig = go.Figure(go.Bar(
            x=counts["count"], y=axis_topics, orientation="h",
            marker={"color": colors[:len(counts)], "line": {"width": 0}},
            customdata=full_topics,
            text=counts["count"], textposition="outside", cliponaxis=False,
            hovertemplate="<b>%{customdata}</b><br>Número de documentos: %{x}<extra></extra>",
        ))
        fig.update_layout(
            height=max(330, 48 * len(counts) + 80), margin={"l": 10, "r": 35, "t": 8, "b": 50},
            paper_bgcolor="white", plot_bgcolor="white", showlegend=False,
            xaxis={"title": "Número de documentos", "gridcolor": "#eceef1", "zeroline": False, "showline": False},
            yaxis={"title": "Tema estratégico", "autorange": "reversed", "showgrid": False, "showline": False},
            font={"color": "#31333F", "size": 12}, hoverlabel={"bgcolor": "white", "font_size": 12},
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_topic_corpus_treemap(filtered_df: pd.DataFrame) -> go.Figure | None:
    """Renderiza la participación temática del corpus filtrado como treemap."""
    counts = build_count_df(filtered_df, "tema_estrategico")
    with st.container(border=True):
        st.markdown("### Participación del corpus por tema")
        st.caption("proporción de documentos asociada a cada tema")
        st.caption("El tamaño de cada bloque representa cuántos documentos corresponden al tema dentro del corpus filtrado. El porcentaje permite comparar su peso relativo.")
        if counts.empty:
            st.info("No hay temas para los filtros seleccionados.")
            return None
        counts = counts.sort_values("count", ascending=False).reset_index(drop=True)
        total = counts["count"].sum()
        full_topics = counts["tema_estrategico"].astype(str).tolist()
        percentages = (counts["count"] / total * 100).round(1).tolist()
        palette = [COLOR_BLUE, COLOR_GREEN, COLOR_ORANGE, COLOR_PURPLE, COLOR_DARK, COLOR_LIGHT_BLUE, COLOR_LIGHT_GREEN, COLOR_GRAY]
        colors = [palette[index % len(palette)] for index in range(len(counts))]
        customdata = [[topic, percentage] for topic, percentage in zip(full_topics, percentages)]
        fig = go.Figure(go.Treemap(
            labels=[short_topic_label(topic) for topic in full_topics],
            parents=[""] * len(counts), values=counts["count"], customdata=customdata,
            marker={"colors": colors, "line": {"color": "white", "width": 3}},
            tiling={"pad": 3},
            texttemplate="<b>%{label}</b><br>%{value} docs<br>%{customdata[1]:.1f}%",
            hovertemplate="<b>%{customdata[0]}</b><br>Documentos: %{value}<br>Participación: %{customdata[1]:.1f}%<extra></extra>",
            textfont={"size": 14, "color": "white"},
        ))
        fig.update_layout(
            height=320, margin={"l": 4, "r": 4, "t": 4, "b": 4},
            paper_bgcolor="white", plot_bgcolor="white",
            hoverlabel={"bgcolor": "white", "font_size": 12, "font_color": "#31333F"},
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        return fig


def _render_topic_relevance(summary: pd.DataFrame) -> None:
    with st.container(border=True):
        st.markdown("### Tema × relevancia para ANE")
        st.caption("heatmap simple, escala 0-10")
        values = summary.dropna(subset=["relevancia_promedio"])
        if values.empty:
            st.info("No hay valores de relevancia para los filtros seleccionados.")
            return
        full_topics = values["tema_estrategico"].astype(str).tolist()
        axis_topics = [shorten_label(topic, 28) for topic in full_topics]
        scores = values["relevancia_promedio"].round(1).to_numpy()[None, :]
        customdata = [full_topics]
        fig = go.Figure(go.Heatmap(
            z=scores, x=axis_topics, y=["Relevancia"], customdata=customdata,
            zmin=0, zmax=10, colorscale=[[0, "#eef3fb"], [.45, COLOR_LIGHT_BLUE], [1, COLOR_PURPLE]],
            text=scores, texttemplate="%{text:.1f}", textfont={"size": 13},
            colorbar={"title": "Promedio", "thickness": 12, "len": .75},
            hovertemplate="<b>%{customdata}</b><br>Relevancia promedio: %{z:.1f}<extra></extra>",
        ))
        fig.update_layout(
            height=330, margin={"l": 10, "r": 25, "t": 8, "b": 95}, paper_bgcolor="white", plot_bgcolor="white",
            xaxis={"title": "Tema estratégico", "tickangle": -28, "showgrid": False, "showline": False},
            yaxis={"title": "Indicador", "showgrid": False, "showline": False},
            font={"color": "#31333F", "size": 11}, hoverlabel={"bgcolor": "white", "font_size": 12},
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_panorama(records: pd.DataFrame) -> None:
    summary = _topic_summary(records, 8)
    high_priority = summary[summary["relevancia_promedio"] >= 7]
    high_topics = set(high_priority["tema_estrategico"])
    concentration = round(records["tema_estrategico"].isin(high_topics).mean() * 100) if len(records) and "tema_estrategico" in records else 0
    sources = sorted(records.get("source_folder", pd.Series(dtype=str)).dropna().astype(str).unique(), key=str.casefold)
    metrics = [
        ("Documentos analizados", len(records), "", "flat"),
        ("Temas identificados", records["tema_estrategico"].nunique() if "tema_estrategico" in records else 0, "agrupación temática validada", "flat"),
        ("Temas de alta prioridad", len(high_priority), f"concentran {concentration}% de señales", "warn"),
        ("Fuentes activas", len(sources), truncate_label(", ".join(sources), 44) or "sin fuentes activas", "flat"),
    ]
    cards = "".join(render_metric_card(label, value, delta, delta_type) for label, value, delta, delta_type in metrics)
    st.markdown(f'<div class="metric-grid panorama-grid">{cards}</div>', unsafe_allow_html=True)
    render_relevance_methodology(records)
    render_section_title("Ranking de temas estratégicos", "UNIVARIADO · POR TEMA")
    _render_topic_volume(records)
    render_topic_corpus_treemap(records)
    _render_topic_relevance(summary)


def _join_unique(series: pd.Series, lists: bool = False) -> str:
    values: list[str] = []
    for value in series:
        candidates = parse_list(value) if lists else [str(value).strip()]
        values.extend(item for item in candidates if item and item not in values)
    return ", ".join(values)


def _build_filtered_signals(records: pd.DataFrame) -> pd.DataFrame:
    keys = ["senal_regulatoria", "tema_estrategico", "linea_pmge", "tipo_insumo_agenda", "relevancia_label"]
    if records.empty or not set(keys).issubset(records.columns):
        return pd.DataFrame()
    signals = records.groupby(keys, dropna=False).agg(
        num_documentos=("document_id", "nunique"), num_fuentes=("source_folder", "nunique"),
        fuentes=("source_folder", _join_unique), tecnologias=("tecnologias", lambda s: _join_unique(s, True)),
        bandas_frecuencia=("bandas_frecuencia", lambda s: _join_unique(s, True)),
        evidencia=("evidencia_breve", _join_unique),
        relevancia_score_promedio=("relevancia_score", "mean"),
        actividad_score_promedio=("actividad_internacional_score", "mean"),
    ).reset_index()
    signals["prioridad_score"] = (signals["relevancia_score_promedio"] + signals["actividad_score_promedio"]).round(2)
    return signals.sort_values("prioridad_score", ascending=False).reset_index(drop=True)


def _priority_label(score: Any, relevance: Any = "", activity: Any = 0) -> tuple[str, str]:
    value = float(score or 0)
    if value >= 10 or (str(relevance).casefold() == "alta" and float(activity or 0) >= 2):
        return "Alta", "high"
    if value >= 8: return "Media-alta", "medium-high"
    if value >= 6: return "Media", "medium"
    if value >= 4: return "Baja-media", "low-medium"
    return "Baja", "low"


def render_signals_table(signals_df: pd.DataFrame) -> str:
    """Renderiza las diez señales principales como tabla HTML ejecutiva."""
    if signals_df.empty:
        st.info("No hay señales disponibles con los filtros actuales.")
        return ""
    badge_classes = {
        "Nueva iniciativa": "signal-new", "Ajuste a iniciativa existente": "signal-adjust",
        "Nota técnica": "signal-note", "Seguimiento": "signal-follow",
        "No prioritario": "signal-low",
    }
    rows: list[str] = []
    for _, row in signals_df.sort_values("prioridad_score", ascending=False).head(10).iterrows():
        signal = str(row.get("senal_regulatoria", ""))
        shown_signal = signal if len(signal) <= 90 else signal[:90].rstrip() + "..."
        input_type = str(row.get("tipo_insumo_agenda", ""))
        priority, priority_class = _priority_label(
            row.get("prioridad_score", 0), row.get("relevancia_label", ""),
            row.get("actividad_score_promedio", 0),
        )
        documents = int(row.get("num_documentos", 0))
        rows.append(
            "<tr>"
            f'<td title="{html.escape(signal, quote=True)}">{html.escape(shown_signal)}</td>'
            f'<td><span class="signal-topic-tag">{html.escape(str(row.get("tema_estrategico", "")))}</span></td>'
            f'<td><strong>{documents} {"doc" if documents == 1 else "docs"}</strong></td>'
            f'<td><span class="signal-badge {badge_classes.get(input_type, "signal-low")}">{html.escape(input_type)}</span></td>'
            f'<td><span class="priority-text priority-{priority_class}">{priority}</span></td>'
            "</tr>"
        )
    table = (
        '<div class="signals-card"><table class="signals-table">'
        '<thead><tr><th>SEÑAL</th><th>TEMA</th><th>EVIDENCIA</th><th>TIPO DE INSUMO</th><th>PRIORIDAD</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>'
    )
    st.markdown(table, unsafe_allow_html=True)
    return table


def _render_signal_method_card() -> None:
    content = (
        '<div class="method-card"><h4>Cómo se construye una señal</h4>'
        '<div class="method-sub">unidad analítica combinada, agrupada por tema</div>'
        '<div class="method-formula">tema + tecnología + banda + fuentes + recencia + relevancia</div>'
        '<div class="method-priorities">'
        '<div class="method-priority"><i class="method-dot" style="background:#D64545"></i><span><b>Prioridad alta</b> — actividad y relevancia altas simultáneamente</span></div>'
        '<div class="method-priority"><i class="method-dot" style="background:#E08E29"></i><span><b>Prioridad media</b> — fuerte en un eje, moderada en el otro</span></div>'
        '<div class="method-priority"><i class="method-dot" style="background:#6b6f7b"></i><span><b>Prioridad baja</b> — bajo volumen y baja relevancia</span></div>'
        '</div></div>'
    )
    st.markdown(content, unsafe_allow_html=True)


def _render_signals(records: pd.DataFrame) -> None:
    signals = _build_filtered_signals(records)
    render_section_title("Radar de señales priorizadas", "DERIVADO / MULTICRITERIO")
    left, right = st.columns([1.45, 1], gap="medium")
    with left:
        with st.container(border=True):
            st.markdown("### Actividad internacional vs. relevancia para ANE")
            st.caption("tamaño = n° de documentos · color = tipo de insumo")
            if signals.empty:
                st.info("No hay señales disponibles con los filtros actuales.")
            else:
                colors = {"Nueva iniciativa": "#1F9C5C", "Ajuste a iniciativa existente": COLOR_ORANGE, "Nota técnica": COLOR_PURPLE, "Seguimiento": COLOR_BLUE, "No prioritario": "#c9ccd4"}
                fig = go.Figure()
                for input_type, group in signals.groupby("tipo_insumo_agenda", sort=False):
                    activity_visual = group["actividad_score_promedio"] * (10 / 3)
                    customdata = list(zip(group["senal_regulatoria"], group["tema_estrategico"], group["relevancia_score_promedio"], group["actividad_score_promedio"], group["num_documentos"], group["fuentes"]))
                    fig.add_trace(go.Scatter(
                        x=activity_visual, y=group["relevancia_score_promedio"], mode="markers", name=input_type,
                        marker={"size": 16 + group["num_documentos"] * 8, "color": colors.get(input_type, COLOR_GRAY), "opacity": .75, "line": {"color": "white", "width": 1}},
                        customdata=customdata,
                        hovertemplate="<b>%{customdata[0]}</b><br>Tema: %{customdata[1]}<br>Tipo de insumo: " + str(input_type) + "<br>Relevancia promedio: %{customdata[2]:.1f}<br>Actividad internacional: %{customdata[3]:.1f} / 3<br>Documentos: %{customdata[4]}<br>Fuentes: %{customdata[5]}<extra></extra>",
                    ))
                fig.update_layout(
                    height=455, margin={"l": 15, "r": 15, "t": 8, "b": 90}, paper_bgcolor="white", plot_bgcolor="white",
                    xaxis={"title": "Actividad internacional (escala visual 0–10)", "range": [0, 10.5], "gridcolor": "#eef0f3", "zeroline": False},
                    yaxis={"title": "Relevancia para ANE", "range": [0, 10.5], "gridcolor": "#eef0f3", "zeroline": False},
                    legend={"orientation": "h", "yanchor": "top", "y": -.22, "xanchor": "center", "x": .5, "title": None, "font": {"size": 9}},
                    hoverlabel={"bgcolor": "white", "font_size": 11, "font_color": "#31333F"},
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    with right:
        _render_signal_method_card()
    render_section_title("Top señales priorizadas")
    render_signals_table(signals)


def filter_regulatory_rows(
    dataframe: pd.DataFrame, topic: str = "Todos", input_type: str = "Todos",
    relevance: str = "Todas", input_column: str = "tipo_insumo_agenda",
) -> pd.DataFrame:
    """Aplica los tres filtros locales sin alterar el subconjunto global de origen."""
    filtered = dataframe.copy()
    if topic != "Todos" and "tema_macro" in filtered.columns:
        filtered = filtered[filtered["tema_macro"].fillna("").astype(str) == topic]
    if input_type != "Todos" and input_column in filtered.columns:
        filtered = filtered[filtered[input_column].fillna("").astype(str) == input_type]
    if relevance != "Todas" and "relevancia_label" in filtered.columns:
        filtered = filtered[filtered["relevancia_label"].fillna("").astype(str) == relevance]
    return filtered.reset_index(drop=True)


def render_regulatory_sunburst(regulatory_map: pd.DataFrame) -> go.Figure | None:
    """Construye el mapa tema macro → subtema con tamaño documental."""
    if regulatory_map.empty:
        return None
    working = regulatory_map.copy()
    working["num_documentos"] = pd.to_numeric(working["num_documentos"], errors="coerce").fillna(0)
    working["relevancia_score_promedio"] = pd.to_numeric(
        working["relevancia_score_promedio"], errors="coerce"
    ).fillna(0)
    children = working.groupby(["tema_macro", "subtema"], dropna=False).agg(
        num_documentos=("num_documentos", "sum"),
        relevancia=("relevancia_score_promedio", "mean"),
        tipo_insumo=("tipo_insumo_agenda", lambda values: values.value_counts().index[0]),
    ).reset_index()
    topics = children.groupby("tema_macro", dropna=False).agg(
        num_documentos=("num_documentos", "sum"), relevancia=("relevancia", "mean"),
        tipo_insumo=("tipo_insumo", lambda values: values.value_counts().index[0]),
    ).reset_index()
    topic_colors = {topic: PALETTE[index % len(PALETTE)] for index, topic in enumerate(topics["tema_macro"])}
    ids = [f"topic::{topic}" for topic in topics["tema_macro"]]
    labels = topics["tema_macro"].astype(str).tolist()
    parents = [""] * len(topics)
    values = topics["num_documentos"].astype(float).tolist()
    colors = [topic_colors[topic] for topic in topics["tema_macro"]]
    customdata = [
        [topic, "Tema macro", relevance, input_type]
        for topic, relevance, input_type in zip(topics["tema_macro"], topics["relevancia"], topics["tipo_insumo"])
    ]
    for _, row in children.iterrows():
        topic, subtopic = str(row["tema_macro"]), str(row["subtema"])
        ids.append(f"sub::{topic}::{subtopic}")
        labels.append(subtopic)
        parents.append(f"topic::{topic}")
        values.append(float(row["num_documentos"]))
        colors.append(topic_colors[topic])
        customdata.append([topic, subtopic, float(row["relevancia"]), str(row["tipo_insumo"])])
    figure = go.Figure(go.Sunburst(
        ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
        marker={"colors": colors, "line": {"color": "#FFFFFF", "width": 2}},
        customdata=customdata,
        hovertemplate=(
            "<b>%{label}</b><br>Tema macro: %{customdata[0]}<br>Subtema: %{customdata[1]}"
            "<br>Documentos: %{value:.0f}<br>Relevancia promedio: %{customdata[2]:.1f}"
            "<br>Tipo de insumo principal: %{customdata[3]}<extra></extra>"
        ),
        insidetextorientation="radial",
    ))
    figure.update_layout(
        height=470, margin={"l": 10, "r": 10, "t": 10, "b": 10},
        paper_bgcolor="white", font={"color": "#31333F", "size": 11},
        hoverlabel={"bgcolor": "white", "font_size": 11, "font_color": "#31333F"},
    )
    return figure


def render_regulatory_map_table(dataframe: pd.DataFrame) -> str:
    """Renderiza la lectura regulatoria como tabla HTML compacta."""
    if dataframe.empty:
        content = '<div class="raw-empty">No hay lecturas regulatorias para los filtros seleccionados.</div>'
        st.markdown(content, unsafe_allow_html=True)
        return content
    input_styles = {
        "Nueva iniciativa": "insumo-new", "Ajuste a iniciativa existente": "insumo-adjust",
        "Nota técnica": "insumo-note", "Seguimiento": "insumo-follow",
        "No prioritario": "insumo-low",
    }
    rows: list[str] = []
    for _, row in dataframe.iterrows():
        relevance = str(row.get("relevancia_label", "Baja"))
        relevance_class = "rel-hi" if relevance == "Alta" else "rel-mid" if relevance == "Media" else "rel-low"
        input_type = str(row.get("tipo_insumo_agenda", "Seguimiento"))
        rows.append(
            "<tr>"
            f'<td><span class="topic-badge">{html.escape(str(row.get("tema_macro", "")))}</span></td>'
            f'<td><div class="two-line">{html.escape(str(row.get("subtema", "")))}</div></td>'
            f'<td><div class="two-line" title="{html.escape(str(row.get("debate_regulatorio", "")), quote=True)}">{html.escape(str(row.get("debate_regulatorio", "")))}</div></td>'
            f'<td><div class="two-line" title="{html.escape(str(row.get("implicacion_regulatoria", "")), quote=True)}">{html.escape(str(row.get("implicacion_regulatoria", "")))}</div></td>'
            f'<td><span class="insumo-badge {input_styles.get(input_type, "insumo-low")}">{html.escape(input_type)}</span></td>'
            f'<td><span class="{relevance_class}">{html.escape(relevance)}</span></td>'
            "</tr>"
        )
    content = (
        '<div class="reg-table-wrap"><table class="reg-table"><thead><tr>'
        '<th>TEMA MACRO</th><th>SUBTEMA</th><th>DEBATE REGULATORIO</th>'
        '<th>IMPLICACIÓN REGULATORIA</th><th>TIPO DE INSUMO</th><th>RELEVANCIA</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )
    st.markdown(content, unsafe_allow_html=True)
    return content


def render_regulatory_trend_cards(trends: pd.DataFrame) -> str:
    """Genera una card por cada tema macro del subconjunto filtrado."""
    if trends.empty:
        content = '<div class="raw-empty">No hay tendencias regulatorias para los filtros seleccionados.</div>'
        st.markdown(content, unsafe_allow_html=True)
        return content
    input_styles = {
        "Nueva iniciativa": "badge-new", "Ajuste a iniciativa existente": "badge-adjust",
        "Nota técnica": "badge-note", "Seguimiento": "badge-follow", "No prioritario": "badge-low",
    }
    cards: list[str] = []
    for _, row in trends.iterrows():
        relevance = str(row.get("relevancia_label", "Baja"))
        relevance_kind = "high" if relevance == "Alta" else "medium" if relevance == "Media" else "low"
        input_type = str(row.get("tipo_insumo_principal", "Seguimiento"))
        fields = [
            ("¿De qué trata?", "de_que_trata"), ("¿Qué está pasando?", "que_esta_pasando"),
            ("¿Por qué importa?", "por_que_importa"), ("Implicación regulatoria", "implicacion_regulatoria"),
        ]
        body = "".join(
            f'<div class="trend-field"><b>{html.escape(label)}</b>{html.escape(str(row.get(column, "")))}</div>'
            for label, column in fields
        )
        cards.append(
            '<article class="trend-card">'
            f'<div class="trend-topic"><span class="topic-badge">{html.escape(str(row.get("tema_asociado", "")))}</span></div>'
            f'<h4>{html.escape(str(row.get("nombre_tendencia", "")))}</h4>{body}'
            '<div class="trend-footer">'
            f'{render_badge(relevance, relevance_kind)}'
            f'<span class="badge {input_styles.get(input_type, "badge-low")}">{html.escape(input_type)}</span>'
            '</div></article>'
        )
    content = f'<div class="trend-grid">{"".join(cards)}</div>'
    st.markdown(content, unsafe_allow_html=True)
    return content


def _regulatory_filter_controls(dataframe: pd.DataFrame, prefix: str, input_column: str) -> tuple[str, str, str]:
    topics = sorted(dataframe.get("tema_macro", pd.Series(dtype=str)).dropna().astype(str).unique(), key=str.casefold)
    inputs = sorted(dataframe.get(input_column, pd.Series(dtype=str)).dropna().astype(str).unique(), key=str.casefold)
    relevances = [value for value in ["Alta", "Media", "Baja"] if value in set(dataframe.get("relevancia_label", []))]
    columns = st.columns(3, gap="medium")
    with columns[0]: topic = st.selectbox("Tema macro", ["Todos"] + topics, key=f"{prefix}_topic")
    with columns[1]: input_type = st.selectbox("Tipo de insumo", ["Todos"] + inputs, key=f"{prefix}_input")
    with columns[2]: relevance = st.selectbox("Relevancia", ["Todas"] + relevances, key=f"{prefix}_relevance")
    return topic, input_type, relevance


def _render_regulatory_map(records: pd.DataFrame) -> None:
    regulatory_map = build_regulatory_map(records)
    with st.container(border=True):
        topic, input_type, relevance = _regulatory_filter_controls(regulatory_map, "reg_map", "tipo_insumo_agenda")
    filtered = filter_regulatory_rows(regulatory_map, topic, input_type, relevance)
    metrics = [
        ("Temas macro identificados", filtered.get("tema_macro", pd.Series(dtype=str)).nunique()),
        ("Subtemas regulatorios", filtered.get("subtema", pd.Series(dtype=str)).nunique()),
        ("Debates activos", filtered.get("debate_regulatorio", pd.Series(dtype=str)).nunique()),
        ("Implicaciones para agenda", filtered.get("implicacion_regulatoria", pd.Series(dtype=str)).nunique()),
    ]
    st.markdown(
        '<div class="metric-grid panorama-grid">' + "".join(render_metric_card(label, value) for label, value in metrics) + "</div>",
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        st.markdown("### División temática del corpus regulatorio")
        st.caption("Cada tema macro se descompone en subtemas regulatorios derivados de las señales procesadas.")
        figure = render_regulatory_sunburst(filtered)
        if figure is None:
            st.info("No hay datos regulatorios para los filtros seleccionados.")
        else:
            st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
    render_section_title("Lectura regulatoria por tema", f"{len(filtered)} lecturas")
    render_regulatory_map_table(filtered)


def _render_regulatory_trends(records: pd.DataFrame) -> None:
    trends = build_regulatory_trends(records)
    with st.container(border=True):
        topic, input_type, relevance = _regulatory_filter_controls(trends, "reg_trends", "tipo_insumo_principal")
    filtered = filter_regulatory_rows(trends, topic, input_type, relevance, "tipo_insumo_principal")
    render_section_title("Tendencias regulatorias explicadas", f"{len(filtered)} temas")
    render_regulatory_trend_cards(filtered)


def _render_regulatory_intelligence(records: pd.DataFrame) -> None:
    st.markdown("## Inteligencia regulatoria")
    subtabs = st.tabs(["Mapa temático regulatorio", "Tendencias regulatorias explicadas"])
    with subtabs[0]:
        st.caption("Organiza los hallazgos del corpus en temas macro, subtemas, debates regulatorios e implicaciones para la Agenda ANE.")
        _render_regulatory_map(records)
    with subtabs[1]:
        st.caption("Traduce los temas tecnológicos detectados en tendencias regulatorias comprensibles, indicando qué está cambiando, por qué importa y qué podría implicar para la ANE.")
        _render_regulatory_trends(records)


def _limit_matrix(matrix: pd.DataFrame, max_rows: int | None = None, max_cols: int | None = None) -> pd.DataFrame:
    """Conserva las categorías con mayor intensidad dentro del filtro activo."""
    limited = matrix
    if max_rows and len(limited.index) > max_rows:
        rows = limited.sum(axis=1).nlargest(max_rows).index
        limited = limited.loc[rows]
    if max_cols and len(limited.columns) > max_cols:
        columns = limited.sum(axis=0).nlargest(max_cols).index
        limited = limited.loc[:, columns]
    return limited


def _mix_hex_colors(low: str, high: str, ratio: float) -> str:
    ratio = max(0.0, min(1.0, ratio))
    low_rgb = tuple(int(low[index:index + 2], 16) for index in (1, 3, 5))
    high_rgb = tuple(int(high[index:index + 2], 16) for index in (1, 3, 5))
    mixed = tuple(round(start + (end - start) * ratio) for start, end in zip(low_rgb, high_rgb))
    return "#" + "".join(f"{value:02X}" for value in mixed)


def _short_source_label(source: Any) -> str:
    aliases = {"Cullen International": "Cullen", "Cullen Intl.": "Cullen", "PolicyTracker": "PolicyTracker", "CRC": "CRC", "UIT/CITEL": "UIT/CITEL"}
    return aliases.get(str(source), shorten_label(str(source), 18))


def _short_input_label(input_type: Any) -> str:
    aliases = {"Nueva iniciativa": "Nueva", "Ajuste a iniciativa existente": "Ajuste", "Nota técnica": "Nota téc.", "Seguimiento": "Seguim.", "No prioritario": "No priorit."}
    return aliases.get(str(input_type), shorten_label(str(input_type), 14))


def render_html_heatmap(
    matrix_df: pd.DataFrame, title: str, subtitle: str, x_label: str, y_label: str,
    note: str, color_palette: tuple[str, str], max_rows: int = 7, max_cols: int = 7,
) -> str:
    """Renderiza una matriz bivariada como heatmap HTML compacto y seguro."""
    matrix = matrix_df.copy()
    if not matrix.empty:
        row_order = matrix.sum(axis=1).sort_values(ascending=False).head(max_rows).index
        if x_label == "Tipo de insumo":
            expected = ["Nueva iniciativa", "Ajuste a iniciativa existente", "Nota técnica", "Seguimiento", "No prioritario"]
            column_order = [column for column in expected if column in matrix.columns][:max_cols]
        else:
            column_order = matrix.sum(axis=0).sort_values(ascending=False).head(max_cols).index.tolist()
        matrix = matrix.loc[row_order, column_order]
    if matrix.empty or matrix.shape[1] == 0:
        content = (
            '<div class="analytics-card">'
            f'<h4>{html.escape(title)}</h4><div class="analytics-subtitle">{html.escape(subtitle)}</div>'
            '<div class="heatmap-note">No hay datos para los filtros seleccionados.</div></div>'
        )
        st.markdown(content, unsafe_allow_html=True)
        return content
    max_value = float(matrix.to_numpy().max()) or 1.0

    def row_name(value: Any) -> str:
        return short_topic_label(str(value)) if "Tema" in y_label else shorten_label(str(value), 20)

    def column_name(value: Any) -> str:
        if x_label == "Fuente": return _short_source_label(value)
        if x_label == "Tipo de insumo": return _short_input_label(value)
        return shorten_label(str(value), 16)

    headers = "".join(
        f'<th title="{html.escape(str(column), quote=True)}">{html.escape(column_name(column))}</th>'
        for column in matrix.columns
    )
    rows: list[str] = []
    for row, values in matrix.iterrows():
        cells: list[str] = []
        for column, raw_value in values.items():
            value = int(raw_value)
            if value == 0:
                background, foreground, shown = "#F5F6F8", "#9A9EA7", "—"
            else:
                ratio = value / max_value
                background = _mix_hex_colors(color_palette[0], color_palette[1], ratio)
                foreground = "#FFFFFF" if ratio >= .58 else "#31333F"
                shown = str(value)
            tooltip = html.escape(f"{row} × {column}: {value} documentos", quote=True)
            cells.append(f'<td style="background:{background};color:{foreground}" title="{tooltip}">{shown}</td>')
        rows.append(
            f'<tr><th class="row-label" title="{html.escape(str(row), quote=True)}">{html.escape(row_name(row))}</th>'
            f'{"".join(cells)}</tr>'
        )
    content = (
        '<div class="analytics-card">'
        f'<h4>{html.escape(title)}</h4><div class="analytics-subtitle">{html.escape(subtitle)}</div>'
        f'<div class="heatmap-axis-x"> {html.escape(x_label)}</div>'
        '<div class="heatmap-scroll"><table class="html-heatmap"><thead><tr>'
        f'<th title="Eje Y: {html.escape(y_label, quote=True)}">· {html.escape(y_label)}</th>{headers}'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
        f'<div class="heatmap-note"><b></b> {html.escape(note)}</div></div>'
    )
    st.markdown(content, unsafe_allow_html=True)
    return content


def render_topic_relevance_bar(filtered_df: pd.DataFrame) -> go.Figure | None:
    """Renderiza relevancia promedio por tema en una barra Plotly compacta."""
    required = {"tema_estrategico", "relevancia_score"}
    with st.container(border=True):
        st.markdown("### Tema × relevancia")
        st.caption("relevancia promedio por tema estratégico en escala 0–10")
        if filtered_df.empty or not required.issubset(filtered_df.columns):
            st.info("No hay datos de relevancia para los filtros seleccionados.")
            return None
        working = filtered_df.copy()
        working["relevancia_score"] = pd.to_numeric(working["relevancia_score"], errors="coerce")
        document_column = "document_id" if "document_id" in working.columns else "tema_estrategico"
        summary = working.groupby("tema_estrategico", dropna=False).agg(
            relevancia_promedio=("relevancia_score", "mean"),
            num_documentos=(document_column, "nunique"),
        ).dropna(subset=["relevancia_promedio"]).reset_index()
        summary = summary.sort_values(["relevancia_promedio", "num_documentos"], ascending=False).head(7)
        if summary.empty:
            st.info("No hay datos de relevancia para los filtros seleccionados.")
            return None
        full_topics = summary["tema_estrategico"].astype(str).tolist()
        colors = [COLOR_BLUE, COLOR_GREEN, COLOR_ORANGE, COLOR_PURPLE, COLOR_DARK, COLOR_LIGHT_BLUE, COLOR_LIGHT_GREEN][:len(summary)]
        customdata = list(zip(full_topics, summary["num_documentos"]))
        fig = go.Figure(go.Bar(
            x=[short_topic_label(topic) for topic in full_topics],
            y=summary["relevancia_promedio"], marker={"color": colors, "line": {"width": 0}},
            customdata=customdata, text=summary["relevancia_promedio"].map(lambda value: f"{value:.1f}"),
            textposition="auto",
            hovertemplate="<b>%{customdata[0]}</b><br>Relevancia promedio: %{y:.1f}<br>Documentos: %{customdata[1]}<extra></extra>",
        ))
        fig.update_layout(
            height=330, margin={"l": 30, "r": 15, "t": 8, "b": 65},
            paper_bgcolor="white", plot_bgcolor="white", showlegend=False,
            xaxis={"title": "Tema estratégico", "showgrid": False, "showline": False, "tickangle": -18},
            yaxis={"title": "Relevancia promedio para ANE", "range": [0, 10], "gridcolor": "#eef0f3", "zeroline": False, "showline": False},
            font={"color": "#31333F", "size": 11}, hoverlabel={"bgcolor": "white", "font_size": 11, "font_color": "#31333F"},
        )
        _, center, _ = st.columns([1, 3, 1])
        with center:
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.caption("Mayor valor indica mayor relevancia promedio del tema para la Agenda ANE.")
        return fig


def _render_crosses(records: pd.DataFrame) -> None:
    st.markdown("## Cruces analíticos")
    st.caption("Relaciones bivariadas entre temas, fuentes, tecnologías, bandas e insumos para agenda.")
    charts = [
        (build_matrix(records, "tema_estrategico", "source_folder"), "Tema estratégico × fuente", "documentos por tema y fuente documental", "Fuente", "Tema estratégico", "Mayor intensidad indica más documentos asociados a ese tema dentro de una fuente.", ("#EAF1FB", COLOR_BLUE)),
        (build_matrix(records, "tema_estrategico", "tecnologias"), "Tema estratégico × tecnología", "coocurrencia entre temas y tecnologías normalizadas", "Tecnología", "Tema estratégico", "Permite ver qué tecnologías concentran la discusión dentro de cada tema.", ("#E8F6F3", COLOR_GREEN)),
        (build_cross_matrix(records, "bandas_frecuencia", "tecnologias"), "Banda × tecnología", "coocurrencia entre bandas de frecuencia y tecnologías", "Tecnología", "Banda de frecuencia", "Identifica qué bandas aparecen asociadas a cada tecnología en los documentos filtrados.", ("#FDEDD6", COLOR_ORANGE)),
        (build_matrix(records, "tema_estrategico", "tipo_insumo_agenda"), "Tema estratégico × tipo de insumo", "posible uso de cada tema para la Agenda Regulatoria", "Tipo de insumo", "Tema estratégico", "Muestra si un tema tiende a sugerir nueva iniciativa, ajuste, nota técnica o seguimiento.", ("#EFE8F8", COLOR_PURPLE)),
    ]
    first_row = st.columns(2, gap="medium")
    second_row = st.columns(2, gap="medium")
    for container, settings in zip(first_row + second_row, charts):
        with container:
            render_html_heatmap(*settings)
    render_topic_relevance_bar(records)


def _raw_topic_label(topic: Any) -> str:
    aliases = {
        "Disponibilidad de espectro para IMT": "Disponibilidad y asignación de espectro",
        "Conectividad satelital, NTN y D2D": "Conectividad satelital / NTN / D2D",
        "Bandas medias y altas para servicios móviles": "Bandas medias y altas para IMT",
        "Spectrum sharing y mecanismos flexibles": "Uso compartido / mecanismos flexibles",
        "6 GHz, Wi-Fi e IMT": "Wi-Fi / 6 GHz",
        "Redes privadas y verticales industriales": "Redes privadas / verticales",
        "Armonización y gestión internacional": "Gestión internacional",
        "Otros temas de seguimiento": "Otros",
    }
    return aliases.get(str(topic), shorten_label(str(topic), 42))


def _display_list_value(value: Any, separator: str) -> str:
    parsed = parse_list(value)
    if parsed:
        return separator.join(parsed)
    raw = "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()
    return raw if raw and raw.casefold() not in {"nan", "none", "[]"} else "—"


def _record_year(row: pd.Series) -> str:
    value = row.get("year", "")
    if value is not None and not pd.isna(value) and str(value).strip():
        text = str(value).strip()
        return text[:-2] if text.endswith(".0") else text
    match = re.search(r"\b(202[4-8])\b", str(row.get("file_name", "")))
    return match.group(1) if match else "—"


def _filter_raw_records(records: pd.DataFrame, query: str = "", topic: str = "Tema: todos") -> pd.DataFrame:
    displayed = records.copy()
    if topic != "Tema: todos" and "tema_estrategico" in displayed.columns:
        displayed = displayed[displayed["tema_estrategico"].fillna("").astype(str) == topic]
    search_columns = [column for column in ["file_name", "senal_regulatoria", "tema_estrategico", "tecnologias", "bandas_frecuencia", "source_folder", "paises_regiones"] if column in displayed.columns]
    if query.strip() and search_columns:
        mask = pd.Series(False, index=displayed.index)
        for column in search_columns:
            mask |= displayed[column].fillna("").astype(str).str.contains(query.strip(), case=False, regex=False)
        displayed = displayed[mask]
    return displayed.reset_index(drop=True)


def render_raw_data_table(dataframe: pd.DataFrame) -> str:
    """Renderiza la base de consulta con nueve columnas ejecutivas."""
    if dataframe.empty:
        content = '<div class="raw-empty">No hay registros con los filtros actuales.</div>'
        st.markdown(content, unsafe_allow_html=True)
        return content
    input_styles = {
        "Nueva iniciativa": ("Nueva", "insumo-new"),
        "Ajuste a iniciativa existente": ("Ajuste", "insumo-adjust"),
        "Nota técnica": ("Nota téc.", "insumo-note"),
        "Seguimiento": ("Seguim.", "insumo-follow"),
        "No prioritario": ("No priorit.", "insumo-low"),
    }
    rows: list[str] = []
    for _, row in dataframe.iterrows():
        signal = str(row.get("senal_regulatoria", "") or "")
        shown_signal = signal if len(signal) <= 80 else signal[:80].rstrip() + "..."
        input_type = str(row.get("tipo_insumo_agenda", "") or "")
        input_label, input_class = input_styles.get(input_type, (input_type or "—", "insumo-low"))
        relevance = pd.to_numeric(pd.Series([row.get("relevancia_score", None)]), errors="coerce").iloc[0]
        if pd.isna(relevance):
            relevance_text, relevance_class = "—", "rel-low"
        else:
            relevance_text = str(int(relevance)) if float(relevance).is_integer() else f"{float(relevance):.1f}"
            relevance_class = "rel-hi" if relevance >= 7 else "rel-mid" if relevance >= 4 else "rel-low"
        country = _display_list_value(row.get("paises_regiones", ""), ", ")
        bands = _display_list_value(row.get("bandas_frecuencia", ""), " / ")
        source = str(row.get("source_folder", "") or "—")
        topic = str(row.get("tema_estrategico", "") or "—")
        rows.append(
            "<tr>"
            f'<td>{html.escape(str(row.get("file_name", "") or "—"))}</td>'
            f'<td><span class="source-pill">{html.escape(source)}</span></td>'
            f'<td>{html.escape(_record_year(row))}</td>'
            f'<td>{html.escape(country)}</td>'
            f'<td title="{html.escape(topic, quote=True)}">{html.escape(_raw_topic_label(topic))}</td>'
            f'<td title="{html.escape(signal, quote=True)}">{html.escape(shown_signal or "—")}</td>'
            f'<td>{html.escape(bands)}</td>'
            f'<td><span class="insumo-badge {input_class}">{html.escape(input_label)}</span></td>'
            f'<td><span class="{relevance_class}">{relevance_text}</span></td>'
            "</tr>"
        )
    content = (
        '<div class="docs-wrap"><table class="docs-table"><thead><tr>'
        '<th>ARCHIVO</th><th>FUENTE</th><th>AÑO</th><th>PAÍS</th><th>TEMA</th><th>SEÑAL</th><th>BANDAS</th><th>TIPO_INSUMO</th><th>REL.</th>'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
    )
    st.markdown(content, unsafe_allow_html=True)
    return content


def _render_raw_data(records: pd.DataFrame) -> None:
    st.markdown('<div class="raw-section-title"><h3>Base procesada</h3><span class="raw-section-pill">CONSULTA / RESPALDO</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="schema-note">schema: archivo · fuente · anio · pais · tema · señal · linea_pmge · bandas · tipo_insumo · relevancia(0-10)</div>', unsafe_allow_html=True)
    topics = sorted(records.get("tema_estrategico", pd.Series(dtype=str)).dropna().astype(str).unique(), key=str.casefold)
    search_column, topic_column = st.columns([3, 1], gap="medium")
    with search_column:
        query = st.text_input("Buscar", placeholder="Buscar por señal, tema, banda, tecnología o archivo...", label_visibility="collapsed", key="raw_search")
    with topic_column:
        selected_topic = st.selectbox("Tema", ["Tema: todos"] + topics, label_visibility="collapsed", key="raw_topic")
    displayed = _filter_raw_records(records, query, selected_topic)
    render_raw_data_table(displayed)
    st.markdown(f'<div class="raw-footnote">{len(displayed)} filas filtradas · datos procesados para demo · sin documentos fuente incluidos</div>', unsafe_allow_html=True)


def _filter_options(frame: pd.DataFrame, column: str) -> list[str]:
    if frame.empty or column not in frame.columns:
        return []
    return sorted(frame[column].fillna("").astype(str).loc[lambda s: s.str.len() > 0].unique(), key=str.casefold)


def _apply_alignment_filters(frame: pd.DataFrame, selections: dict[str, Any]) -> pd.DataFrame:
    filtered = frame.copy()
    for column, selected in selections.items():
        if column == "min_score" or column not in filtered.columns or not selected:
            continue
        choices = {str(item).casefold() for item in selected}
        filtered = filtered[filtered[column].fillna("").astype(str).str.casefold().isin(choices)]
    score_column = "opportunity_score" if "opportunity_score" in filtered.columns else "alignment_score"
    if score_column in filtered.columns:
        filtered[score_column] = pd.to_numeric(filtered[score_column], errors="coerce").fillna(0)
        filtered = filtered[filtered[score_column] >= float(selections.get("min_score", 0))]
    return filtered.reset_index(drop=True)


def render_categorical_heatmap(frame: pd.DataFrame, row_col: str, col_col: str, value_col: str, title: str, note: str, max_rows: int = 8, max_cols: int = 8) -> str:
    with st.container(border=True):
        st.markdown(f"### {title}")
        if frame.empty or not {row_col, col_col, value_col}.issubset(frame.columns):
            st.info("No hay datos para construir el heatmap.")
            return ""
        score_col = "opportunity_score" if "opportunity_score" in frame.columns else "alignment_score"
        working = frame.copy()
        working[score_col] = pd.to_numeric(working[score_col], errors="coerce").fillna(0)
        rows = working.groupby(row_col)[score_col].max().sort_values(ascending=False).head(max_rows).index.tolist()
        cols = working.groupby(col_col)[score_col].max().sort_values(ascending=False).head(max_cols).index.tolist()
        pivot = working.sort_values(score_col, ascending=False).drop_duplicates([row_col, col_col]).set_index([row_col, col_col])[value_col]
        headers = "".join(f'<th title="{html.escape(str(col), quote=True)}">{html.escape(short_label(col, 18))}</th>' for col in cols)
        class_map = {"Alta relación": "hm-status-alta", "Alta": "hm-status-alta", "Parcial": "hm-status-parcial", "Brecha": "hm-status-brecha", "Débil": "hm-status-brecha", "S/E": "hm-status-se"}
        body: list[str] = []
        for row in rows:
            cells = []
            for col in cols:
                status = pivot.get((row, col), "S/E")
                cells.append(f'<td class="{class_map.get(str(status), "hm-status-se")}" title="{html.escape(str(row), quote=True)} × {html.escape(str(col), quote=True)}">{html.escape(short_label(status, 12))}</td>')
            body.append(f'<tr><th class="row-label" title="{html.escape(str(row), quote=True)}">{html.escape(short_label(row, 24))}</th>{"".join(cells)}</tr>')
        content = f'<div class="heatmap-scroll"><table class="html-heatmap"><thead><tr><th></th>{headers}</tr></thead><tbody>{"".join(body)}</tbody></table></div><div class="heatmap-note">{html.escape(note)}</div>'
        st.markdown(content, unsafe_allow_html=True)
        return content


def render_alignment_ranking(frame: pd.DataFrame, group_col: str, score_col: str, title: str) -> go.Figure | None:
    with st.container(border=True):
        st.markdown(f"### {title}")
        if frame.empty or not {group_col, score_col}.issubset(frame.columns):
            st.info("No hay datos para el ranking.")
            return None
        summary = frame.copy()
        summary[score_col] = pd.to_numeric(summary[score_col], errors="coerce").fillna(0)
        summary = summary.groupby(group_col, dropna=False)[score_col].max().sort_values(ascending=True).tail(8).reset_index()
        fig = go.Figure(go.Bar(x=summary[score_col], y=[short_label(value, 34) for value in summary[group_col]], orientation="h", marker={"color": COLOR_BLUE}, customdata=summary[group_col], hovertemplate="<b>%{customdata}</b><br>Score: %{x:.1f}<extra></extra>"))
        fig.update_layout(height=330, margin={"l": 20, "r": 20, "t": 8, "b": 30}, paper_bgcolor="white", plot_bgcolor="white", xaxis={"range": [0, 100], "gridcolor": "#eef0f3"}, yaxis={"title": ""}, showlegend=False, font={"size": 11, "color": "#31333F"})
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        return fig


def render_methodology_card(title: str, weights: list[tuple[str, int]]) -> str:
    rows = "".join(f'<div class="weight-row"><div class="w-lbl">{html.escape(label)}</div><div class="w-bar"><div class="w-fill" style="width:{weight}%"></div></div><div class="w-pct">{weight}%</div></div>' for label, weight in weights)
    content = f'<div class="align-card"><h4>{html.escape(title)}</h4>{rows}</div>'
    st.markdown(content, unsafe_allow_html=True)
    return content


def render_document_opportunity_cards(frame: pd.DataFrame) -> str:
    rows = []
    for _, row in frame.sort_values("opportunity_score", ascending=False).head(4).iterrows():
        rows.append('<div class="align-card">' + f'<div>{render_badge(row.get("score_label", ""), _badge_kind(row.get("score_label", "")))}</div><h4>{html.escape(str(row.get("policy_activity_name", "—")))}</h4>' + f'<div class="align-field"><b>Política pública / matriz</b>{html.escape(str(row.get("policy_name", "—")))}</div><div class="align-field"><b>Tendencia documental que la alimenta</b>{html.escape(str(row.get("trend_name", "—")))}</div><div class="align-field"><b>Documentos soporte</b>{render_doc_pills(row.get("support_documents", ""))}</div><div class="align-field"><b>Evidencia encontrada en el repo</b>{html.escape(shorten_label(str(row.get("documentary_evidence", "—")), 260))}</div><div class="align-field"><b>Qué debería ajustarse o profundizarse</b>{html.escape(str(row.get("coverage_status", "—")))}</div><div class="align-field"><b>Recomendación</b>{render_badge(row.get("recommendation", "—"), _badge_kind(row.get("recommendation", "")))}</div><div class="align-field"><b>Score</b>{float(row.get("opportunity_score", 0)):.1f}</div></div>')
    content = '<div class="align-grid">' + "".join(rows) + "</div>" if rows else '<div class="raw-empty">No hay oportunidades priorizadas.</div>'
    st.markdown(content, unsafe_allow_html=True)
    return content


def render_pmge_priority_cards(frame: pd.DataFrame) -> str:
    rows = []
    for _, row in frame.sort_values("alignment_score", ascending=False).head(4).iterrows():
        rows.append('<div class="align-card">' + f'<div>{render_badge(row.get("alignment_level", ""), _badge_kind(row.get("alignment_level", "")))}</div><h4>{html.escape(str(row.get("project_name", "—")))}</h4>' + f'<div class="align-field"><b>Documento fuente</b>{html.escape(str(row.get("source_document", "—")))}</div><div class="align-field"><b>Política pública / actividad matriz</b>{html.escape(str(row.get("policy_name", "—")))} / {html.escape(str(row.get("policy_activity_name", "—")))}</div><div class="align-field"><b>Línea temática PMGE</b>{html.escape(str(row.get("pmge_line", "—")))}</div><div class="align-field"><b>Por qué se relacionan</b>{html.escape(str(row.get("observation", "—")))}</div><div class="align-field"><b>Qué refuerza / qué podría complementarse</b>{html.escape(str(row.get("alignment_level", "—")))}</div><div class="align-field"><b>Acción sugerida</b>{render_badge(row.get("suggested_action", "—"), _badge_kind(row.get("suggested_action", "")))}</div><div class="align-field"><b>Score</b>{float(row.get("alignment_score", 0)):.1f}</div></div>')
    content = '<div class="align-grid">' + "".join(rows) + "</div>" if rows else '<div class="raw-empty">No hay proyectos priorizados.</div>'
    st.markdown(content, unsafe_allow_html=True)
    return content


def _render_document_policy_alignment(frame: pd.DataFrame) -> None:
    st.markdown('<div class="align-source-note">Fuente: documentos del repositorio de vigilancia (Cullen Intl. · CRC · UIT/CITEL) — no incluye PMGE</div>', unsafe_allow_html=True)
    with st.container(border=True):
        cols = st.columns([1, 1, 1, 1, .9], gap="medium")
        selections = {"trend_name": cols[0].multiselect("Tendencia documental", _filter_options(frame, "trend_name"), key="doc_align_trend"), "policy_activity_name": cols[1].multiselect("Actividad de política pública", _filter_options(frame, "policy_activity_name"), key="doc_align_activity"), "coverage_status": cols[2].multiselect("Estado de cobertura", _filter_options(frame, "coverage_status"), key="doc_align_status"), "recommendation": cols[3].multiselect("Recomendación", _filter_options(frame, "recommendation"), key="doc_align_reco"), "min_score": cols[4].slider("Score mínimo", 0, 100, 0, key="doc_align_score")}
    filtered = _apply_alignment_filters(frame, selections)
    metrics = [("Tendencias documentales cruzadas", filtered.get("trend_name", pd.Series(dtype=str)).nunique()), ("Actividades de matriz impactadas", filtered.get("policy_activity_id", pd.Series(dtype=str)).nunique()), ("Oportunidades altas", int((filtered.get("score_label", pd.Series(dtype=str)) == "Alta").sum())), ("Brechas documentales", int(filtered.get("coverage_status", pd.Series(dtype=str)).isin(["Brecha", "S/E"]).sum()))]
    st.markdown('<div class="metric-grid panorama-grid">' + "".join(render_metric_card(label, value) for label, value in metrics) + "</div>", unsafe_allow_html=True)
    render_categorical_heatmap(filtered, "trend_name", "policy_activity_name", "coverage_status", "Cobertura documental frente a actividades de política pública", "Eje Y: trend_name o topic_macro. Eje X: policy_activity_name abreviado.")
    render_alignment_ranking(filtered, "policy_activity_name", "opportunity_score", "Top actividades de política que pueden alimentarse con vigilancia documental")
    render_section_title("Lectura de oportunidad documental", f"{len(filtered)} cruces")
    render_html_table(filtered, [("trend_name", "Tendencia documental"), ("support_documents", "Documentos soporte"), ("policy_activity_name", "Política / actividad de matriz"), ("coverage_status", "Estado de cobertura"), ("documentary_evidence", "Evidencia documental"), ("recommendation", "Recomendación"), ("opportunity_score", "Score")])
    render_section_title("Oportunidades priorizadas")
    render_document_opportunity_cards(filtered)
    render_section_title("Cómo se calcula el score")
    render_methodology_card("Score de oportunidad documental", [("relevancia_tendencia_documental", 30), ("brecha_actividad_politica", 25), ("evidencia_acumulada", 20), ("recencia_actualidad", 15), ("accionabilidad_regulatoria", 10)])


def _render_pmge_policy_alignment(frame: pd.DataFrame) -> None:
    st.markdown('<div class="align-source-note">Fuente: proyectos del PMGE / Agenda Regulatoria</div>', unsafe_allow_html=True)
    with st.container(border=True):
        cols = st.columns([1, 1, 1, 1, .9], gap="medium")
        selections = {"project_name": cols[0].multiselect("Proyecto PMGE / Agenda", _filter_options(frame, "project_name"), key="pmge_align_project"), "policy_activity_name": cols[1].multiselect("Actividad de matriz", _filter_options(frame, "policy_activity_name"), key="pmge_align_activity"), "pmge_line": cols[2].multiselect("Línea temática PMGE", _filter_options(frame, "pmge_line"), key="pmge_align_line"), "alignment_level": cols[3].multiselect("Nivel de alineación", _filter_options(frame, "alignment_level"), key="pmge_align_level"), "min_score": cols[4].slider("Temporalidad / score mínimo", 0, 100, 0, key="pmge_align_score")}
    filtered = _apply_alignment_filters(frame, selections)
    metrics = [("Proyectos PMGE cruzados", filtered.get("project_id", pd.Series(dtype=str)).nunique()), ("Actividades de matriz relacionadas", filtered.get("policy_activity_id", pd.Series(dtype=str)).nunique()), ("Alta alineación", int((filtered.get("alignment_level", pd.Series(dtype=str)) == "Alta").sum())), ("Posibles vacíos", int(filtered.get("alignment_level", pd.Series(dtype=str)).isin(["Débil", "S/E"]).sum()))]
    st.markdown('<div class="metric-grid panorama-grid">' + "".join(render_metric_card(label, value) for label, value in metrics) + "</div>", unsafe_allow_html=True)
    render_categorical_heatmap(filtered, "project_name", "policy_activity_name", "alignment_level", "Alineación entre proyectos PMGE y actividades de política pública", "Los nombres completos de proyectos, documentos fuente y actividades de matriz se detallan en la tabla inferior.")
    render_alignment_ranking(filtered, "project_name", "alignment_score", "Proyectos PMGE con mayor alineación con la matriz")
    render_section_title("Cruce proyecto PMGE vs actividad de política", f"{len(filtered)} cruces")
    render_html_table(filtered, [("project_name", "Proyecto PMGE / Agenda"), ("source_document", "Documento fuente"), ("policy_activity_name", "Política / actividad de matriz"), ("pmge_line", "Línea temática PMGE"), ("alignment_level", "Nivel"), ("observation", "Observación"), ("suggested_action", "Acción sugerida"), ("alignment_score", "Score")])
    render_section_title("Proyectos priorizados")
    render_pmge_priority_cards(filtered)
    render_section_title("Cómo se calcula el score")
    render_methodology_card("Score de alineación institucional", [("coincidencia_tematica", 35), ("coincidencia_objetivos", 25), ("relacion_actividades_matriz", 20), ("temporalidad_compatible", 10), ("potencial_implementacion", 10)])


def _render_strategic_alignment(data: dict[str, pd.DataFrame]) -> None:
    st.markdown("## Alineación estratégica")
    subtabs = st.tabs(["Vigilancia documental × Matriz de políticas", "PMGE / Agenda × Matriz de políticas"])
    with subtabs[0]:
        _render_document_policy_alignment(data.get("dashboard_document_policy_alignment", pd.DataFrame()))
    with subtabs[1]:
        _render_pmge_policy_alignment(data.get("dashboard_pmge_policy_alignment", pd.DataFrame()))


def main() -> None:
    st.set_page_config(
        page_title="Vigilancia Tecnológica ANE",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.title("Vigilancia Tecnológica — PMGE 2026-2030 / Agenda ANE 2027-2028")
    st.caption("Insumo técnico para formulación de agenda regulatoria · señales derivadas de fuentes documentales externas e institucionales")
    if dashboard_data_source() == DASHBOARD_DATA_SOURCE_SUPABASE:
        render_supabase_upload_panel()
        try:
            render_supabase_dashboard(load_published_dashboard_model())
        except NoPublishedAnalysisRunError:
            render_no_published_dashboard_state()
        except IncompletePublishedRunError as exc:
            render_no_published_dashboard_state(str(exc))
        return

    data = load_demo_data()
    records = data.get("dashboard_records", pd.DataFrame())
    if records.empty:
        st.warning("No hay registros procesados disponibles en demo_data.")
        return
    filters = _render_filters(records)
    filtered = apply_global_filters(records, filters)
    st.sidebar.markdown(
        render_metric_card("Registros visibles", len(filtered)),
        unsafe_allow_html=True,
    )
    tabs = st.tabs(["Panorama estratégico", "Inteligencia regulatoria", "Señales emergentes y oportunidades", "Cruces analíticos", "Alineación estratégica", "Base procesada"])
    with tabs[0]: _render_panorama(filtered)
    with tabs[1]: _render_regulatory_intelligence(filtered)
    with tabs[2]: _render_signals(filtered)
    with tabs[3]: _render_crosses(filtered)
    with tabs[4]: _render_strategic_alignment(data)
    with tabs[5]: _render_raw_data(filtered)

if __name__ == "__main__":
    main()
