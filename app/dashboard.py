"""Dashboard Streamlit para presentar los resultados del MVP."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import STRUCTURED_DATA_DIR


FILES = {
    "document_texts": STRUCTURED_DATA_DIR / "document_texts.csv",
    "structured_documents": STRUCTURED_DATA_DIR / "structured_documents.csv",
    "technologies": STRUCTURED_DATA_DIR / "llm_tecnologias.csv",
    "bands": STRUCTURED_DATA_DIR / "llm_bandas_frecuencia.csv",
    "countries": STRUCTURED_DATA_DIR / "llm_paises.csv",
    "organizations": STRUCTURED_DATA_DIR / "llm_organizaciones.csv",
    "relevance": STRUCTURED_DATA_DIR / "llm_relevancia_agenda_ane.csv",
    "document_types": STRUCTURED_DATA_DIR / "llm_tipo_documento.csv",
}

REPORTS = {
    "Reporte exploratorio del corpus": STRUCTURED_DATA_DIR / "corpus_report.md",
    "Análisis de resultados LLM": STRUCTURED_DATA_DIR / "llm_analysis_report.md",
}


@st.cache_data(show_spinner=False)
def load_csv(path: Path) -> pd.DataFrame | None:
    """Carga un CSV; devuelve None si no existe o no puede leerse."""
    if not path.is_file():
        return None
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except (OSError, UnicodeError, pd.errors.ParserError):
        return None


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
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            try:
                parsed = ast.literal_eval(raw)
            except (ValueError, SyntaxError):
                return []
    if isinstance(parsed, str):
        parsed = [parsed]
    if not isinstance(parsed, (list, tuple, set)):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def _clean_scalar(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return " ".join(str(value).split())


def _unique_options(dataframe: pd.DataFrame | None, column: str) -> list[str]:
    if dataframe is None or column not in dataframe.columns:
        return []
    values = {_clean_scalar(value) for value in dataframe[column]}
    return sorted((value for value in values if value), key=str.casefold)


def _list_options(dataframe: pd.DataFrame | None, column: str) -> list[str]:
    if dataframe is None or column not in dataframe.columns:
        return []
    values = {item for value in dataframe[column] for item in parse_list(value)}
    return sorted(values, key=str.casefold)


def _matches_selected_list(value: Any, selected: list[str]) -> bool:
    if not selected:
        return True
    available = {item.casefold() for item in parse_list(value)}
    return bool(available.intersection(item.casefold() for item in selected))


def apply_filters(dataframe: pd.DataFrame | None, filters: dict[str, list[str]]) -> pd.DataFrame:
    """Aplica filtros escalares y de listas a los resultados estructurados."""
    if dataframe is None:
        return pd.DataFrame()
    filtered = dataframe.copy()
    for column in ("source_folder", "relevancia_agenda_ane", "tipo_documento"):
        selected = filters.get(column, [])
        if selected and column in filtered.columns:
            normalized = {item.casefold() for item in selected}
            values = filtered[column].fillna("").astype(str).str.strip().str.casefold()
            filtered = filtered[values.isin(normalized)]
    for column in ("tecnologias", "paises", "organizaciones"):
        selected = filters.get(column, [])
        if selected and column in filtered.columns:
            filtered = filtered[
                filtered[column].apply(lambda value: _matches_selected_list(value, selected))
            ]
    return filtered


def _top_value(dataframe: pd.DataFrame | None) -> str:
    if dataframe is None or dataframe.empty:
        return "No disponible"
    return _clean_scalar(dataframe.iloc[0, 0]) or "No disponible"


def _metric_values(data: dict[str, pd.DataFrame | None]) -> dict[str, Any]:
    corpus = data["document_texts"]
    structured = data["structured_documents"]
    if corpus is None:
        rows, unique_documents, top_source = 0, 0, "No disponible"
    else:
        rows = len(corpus)
        unique_key = "file_path" if "file_path" in corpus.columns else "document_id"
        unique_documents = corpus[unique_key].nunique() if unique_key in corpus.columns else rows
        if {unique_key, "source_folder"}.issubset(corpus.columns):
            counts = (
                corpus.drop_duplicates(unique_key)["source_folder"]
                .replace("", pd.NA)
                .dropna()
                .value_counts()
            )
            top_source = str(counts.index[0]) if not counts.empty else "No disponible"
        else:
            top_source = "No disponible"
    if structured is None or structured.empty:
        llm_documents, llm_ok_percentage = 0, 0.0
    else:
        llm_documents = len(structured)
        if "llm_status" in structured.columns:
            ok = structured["llm_status"].fillna("").astype(str).str.casefold().eq("ok").sum()
            llm_ok_percentage = ok / llm_documents * 100
        else:
            llm_ok_percentage = 0.0
    return {
        "unique_documents": unique_documents,
        "rows": rows,
        "llm_documents": llm_documents,
        "llm_ok_percentage": llm_ok_percentage,
        "top_source": top_source,
        "top_technology": _top_value(data["technologies"]),
        "top_band": _top_value(data["bands"]),
        "top_relevance": _top_value(data["relevance"]),
    }


def _render_summary(data: dict[str, pd.DataFrame | None]) -> None:
    st.header("Resumen general")
    metrics = _metric_values(data)
    first = st.columns(4)
    first[0].metric("Documentos únicos del corpus", f"{metrics['unique_documents']:,}")
    first[1].metric("Filas procesadas", f"{metrics['rows']:,}")
    first[2].metric("Documentos analizados por LLM", f"{metrics['llm_documents']:,}")
    first[3].metric("Extracciones LLM correctas", f"{metrics['llm_ok_percentage']:.1f}%")
    second = st.columns(4)
    second[0].metric("Fuente más frecuente", metrics["top_source"])
    second[1].metric("Tecnología más recurrente", metrics["top_technology"])
    second[2].metric("Banda más recurrente", metrics["top_band"])
    second[3].metric("Relevancia mayoritaria", metrics["top_relevance"])


def _render_sidebar(structured: pd.DataFrame | None) -> dict[str, list[str]]:
    st.sidebar.header("Filtros")
    st.sidebar.caption("Deja un filtro vacío para incluir todos los valores.")
    return {
        "source_folder": st.sidebar.multiselect(
            "Fuente documental", _unique_options(structured, "source_folder")
        ),
        "relevancia_agenda_ane": st.sidebar.multiselect(
            "Relevancia Agenda ANE", _unique_options(structured, "relevancia_agenda_ane")
        ),
        "tipo_documento": st.sidebar.multiselect(
            "Tipo de documento", _unique_options(structured, "tipo_documento")
        ),
        "tecnologias": st.sidebar.multiselect(
            "Tecnología", _list_options(structured, "tecnologias")
        ),
        "paises": st.sidebar.multiselect("País", _list_options(structured, "paises")),
        "organizaciones": st.sidebar.multiselect(
            "Organización", _list_options(structured, "organizaciones")
        ),
    }


def _bar_chart(dataframe: pd.DataFrame | None, label: str, title: str, limit: int = 12) -> None:
    st.subheader(title)
    required = {label, "count"}
    if dataframe is None or dataframe.empty or not required.issubset(dataframe.columns):
        st.info("No hay datos disponibles para esta visualización.")
        return
    st.bar_chart(
        dataframe[[label, "count"]].head(limit).set_index(label),
        horizontal=True,
        width="stretch",
    )


def _render_corpus_tab(corpus: pd.DataFrame | None) -> None:
    if corpus is None:
        st.warning("No se puede mostrar el corpus porque falta document_texts.csv.")
        return
    summary_columns = [
        column
        for column in (
            "document_id", "file_name", "source_folder", "file_type",
            "sheet_name", "num_chars", "status",
        )
        if column in corpus.columns
    ]
    st.subheader("Documentos procesados")
    st.dataframe(corpus[summary_columns], width="stretch", hide_index=True)
    columns = st.columns(3)
    for container, column, title in zip(
        columns,
        ("source_folder", "file_type", "status"),
        ("Documentos por fuente", "Tipos de archivo", "Estados de procesamiento"),
    ):
        with container:
            st.subheader(title)
            if column in corpus.columns:
                st.bar_chart(corpus[column].fillna("Sin especificar").value_counts())
            else:
                st.info("Dato no disponible.")


def _render_llm_tab(filtered: pd.DataFrame) -> None:
    if filtered.empty:
        st.info("No hay resultados LLM para los filtros seleccionados.")
        return
    columns = [
        column
        for column in (
            "file_name", "source_folder", "tema_principal", "tecnologias",
            "bandas_frecuencia", "paises", "organizaciones",
            "relevancia_agenda_ane", "resumen",
        )
        if column in filtered.columns
    ]
    st.caption(f"{len(filtered)} documento(s) coinciden con los filtros.")
    st.dataframe(filtered[columns], width="stretch", hide_index=True)


def _render_trends_tab(data: dict[str, pd.DataFrame | None]) -> None:
    left, right = st.columns(2)
    with left:
        _bar_chart(data["technologies"], "tecnologia", "Tecnologías más recurrentes")
        _bar_chart(data["countries"], "pais", "Países más recurrentes")
        _bar_chart(data["relevance"], "relevancia_agenda_ane", "Relevancia para la Agenda ANE")
    with right:
        _bar_chart(data["bands"], "banda_frecuencia", "Bandas más recurrentes")
        _bar_chart(data["organizations"], "organizacion", "Organizaciones más recurrentes")
        _bar_chart(data["document_types"], "tipo_documento", "Tipos de documento")


def _display_list_field(label: str, value: Any) -> None:
    values = parse_list(value)
    st.markdown(f"**{label}:** {', '.join(values) if values else 'No identificado'}")


def _render_detail_tab(filtered: pd.DataFrame) -> None:
    if filtered.empty:
        st.info("No hay documentos disponibles para mostrar.")
        return
    options = list(filtered.index)

    def format_option(index: Any) -> str:
        row = filtered.loc[index]
        name = _clean_scalar(row.get("file_name", "Documento"))
        identifier = _clean_scalar(row.get("document_id", index))
        return f"{name} — {identifier}"

    selected = st.selectbox("Selecciona un documento", options, format_func=format_option)
    row = filtered.loc[selected]
    st.subheader(_clean_scalar(row.get("file_name", "Documento sin nombre")))
    header = st.columns(3)
    header[0].metric("Fuente", _clean_scalar(row.get("source_folder")) or "No identificada")
    header[1].metric("Tipo", _clean_scalar(row.get("tipo_documento")) or "No identificado")
    header[2].metric("Relevancia", _clean_scalar(row.get("relevancia_agenda_ane")) or "No identificada")
    st.markdown(f"**Tema principal:** {_clean_scalar(row.get('tema_principal')) or 'No identificado'}")
    for column, label in (
        ("temas_secundarios", "Temas secundarios"),
        ("tecnologias", "Tecnologías"),
        ("bandas_frecuencia", "Bandas de frecuencia"),
        ("paises", "Países"),
        ("organizaciones", "Organizaciones"),
        ("actores", "Actores"),
    ):
        _display_list_field(label, row.get(column, ""))
    st.markdown("#### Justificación de relevancia")
    st.write(_clean_scalar(row.get("justificacion_relevancia")) or "No disponible")
    st.markdown("#### Resumen")
    st.write(_clean_scalar(row.get("resumen")) or "No disponible")


def _render_reports_tab() -> None:
    for title, path in REPORTS.items():
        st.subheader(title)
        if path.is_file():
            try:
                st.markdown(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError) as exc:
                st.warning(f"No fue posible leer {path.name}: {exc}")
        else:
            st.warning(f"No se encontró el reporte {path.name}.")
        st.divider()


def main() -> None:
    st.set_page_config(
        page_title="MVP - Vigilancia Tecnológica ANE",
        page_icon="📡",
        layout="wide",
    )
    st.title("MVP - Vigilancia Tecnológica ANE")
    st.caption(
        "Análisis documental para identificación de tendencias, tecnologías, "
        "bandas de frecuencia y señales emergentes"
    )
    data = {name: load_csv(path) for name, path in FILES.items()}
    missing = [path.name for name, path in FILES.items() if data[name] is None]
    if missing:
        st.warning(
            "Algunos archivos no están disponibles o no pudieron leerse: "
            + ", ".join(missing)
            + ". Las secciones restantes seguirán funcionando."
        )
    filters = _render_sidebar(data["structured_documents"])
    filtered = apply_filters(data["structured_documents"], filters)
    _render_summary(data)
    tabs = st.tabs(
        ["Corpus documental", "Resultados LLM", "Tendencias", "Detalle por documento", "Reportes"]
    )
    with tabs[0]:
        _render_corpus_tab(data["document_texts"])
    with tabs[1]:
        _render_llm_tab(filtered)
    with tabs[2]:
        _render_trends_tab(data)
    with tabs[3]:
        _render_detail_tab(filtered)
    with tabs[4]:
        _render_reports_tab()


if __name__ == "__main__":
    main()
