"""Construye CSV procesados y publicables para el dashboard de demo, sin LLM."""
from __future__ import annotations
import json
import logging
import shutil
from pathlib import Path
from typing import Any
import pandas as pd

try:
    from app.config import PROJECT_ROOT, STRUCTURED_DATA_DIR
    from app.topic_taxonomy import infer_tema_estrategico, infer_tipo_evento_regulatorio, map_tema_to_linea_pmge, normalize_bands, normalize_technologies, parse_list_field
except ModuleNotFoundError:  # Ejecución directa: python app/dashboard_data_builder.py
    from config import PROJECT_ROOT, STRUCTURED_DATA_DIR
    from topic_taxonomy import infer_tema_estrategico, infer_tipo_evento_regulatorio, map_tema_to_linea_pmge, normalize_bands, normalize_technologies, parse_list_field

LOGGER = logging.getLogger(__name__)
INPUT_CSV = STRUCTURED_DATA_DIR / "structured_documents.csv"
DEMO_DATA_DIR = PROJECT_ROOT / "demo_data"
OUTPUT_NAMES = ["dashboard_records.csv", "dashboard_signals.csv", "dashboard_temas_counts.csv", "dashboard_relevancia_counts.csv", "dashboard_tipo_insumo_counts.csv", "dashboard_tecnologias_counts.csv", "dashboard_bandas_counts.csv", "dashboard_tema_fuente_matrix.csv", "dashboard_tema_tecnologia_matrix.csv", "dashboard_banda_tecnologia_matrix.csv", "dashboard_tema_tipo_insumo_matrix.csv", "dashboard_tema_relevancia_matrix.csv"]
INTERNATIONAL_SOURCES = ("cullen international", "policytracker", "gsma", "worldbank", "world bank", "reguladores", "uit", "citel", "itu")

def _text(row: pd.Series, column: str) -> str:
    value = row.get(column, "")
    return "" if pd.isna(value) else str(value).strip()

def _is_international_source(value: Any) -> bool:
    source = str(value or "").casefold()
    return any(name in source for name in INTERNATIONAL_SOURCES)

def calculate_relevance_score(row: pd.Series) -> tuple[int, str]:
    """Calcula relevancia 0–10 según las reglas explícitas del MVP."""
    score = {"alta": 4, "media": 2, "baja": 1}.get(_text(row, "relevancia_agenda_ane").casefold(), 0)
    score += 2 if _text(row, "linea_pmge") else 0
    score += 1 if parse_list_field(row.get("tecnologias", [])) else 0
    score += 1 if parse_list_field(row.get("bandas_frecuencia", [])) else 0
    score += 1 if _is_international_source(row.get("source_folder", "")) else 0
    score += 1 if _text(row, "tipo_insumo_agenda") != "No prioritario" else 0
    score = min(score, 10)
    return score, "Baja" if score <= 3 else "Media" if score <= 6 else "Alta"

def calculate_activity_score(row: pd.Series) -> int:
    """Calcula actividad internacional 0–3."""
    return min(3, sum([_is_international_source(row.get("source_folder", "")), bool(parse_list_field(row.get("paises_regiones", []))), bool(parse_list_field(row.get("organizaciones", [])) or parse_list_field(row.get("actores", [])))]))

def _infer_input_type(relevance: str, topic: str) -> str:
    """Regla simple: baja→no prioritario; media→seguimiento; alta→insumo por tema."""
    relevance = relevance.casefold()
    if relevance == "baja": return "No prioritario"
    if relevance == "media": return "Seguimiento"
    if relevance == "alta":
        if topic == "Spectrum sharing y mecanismos flexibles": return "Nueva iniciativa"
        if topic == "Conectividad satelital, NTN y D2D": return "Nota técnica"
        if topic == "Disponibilidad de espectro para IMT": return "Ajuste a iniciativa existente"
    return "Seguimiento"

def _make_record(row: pd.Series) -> dict[str, Any]:
    technologies = normalize_technologies(row.get("tecnologias", []))
    bands = normalize_bands(row.get("bandas_frecuencia", []))
    main = _text(row, "tema_principal")
    keywords = parse_list_field(row.get("palabras_clave", []))
    signal = main or ", ".join(keywords) or _text(row, "file_name")
    topic = infer_tema_estrategico(technologies, bands, signal, main, _text(row, "resumen"))
    line = map_tema_to_linea_pmge(topic)
    input_type = _infer_input_type(_text(row, "relevancia_agenda_ane"), topic)
    evidence = [topic]
    if technologies: evidence.append("tecnologías: " + ", ".join(technologies[:4]))
    if bands: evidence.append("bandas: " + ", ".join(bands[:4]))
    record: dict[str, Any] = {
        "document_id": _text(row, "document_id"), "file_name": _text(row, "file_name"), "source_folder": _text(row, "source_folder"), "file_type": _text(row, "file_type"),
        "tema_estrategico": topic, "linea_pmge": line, "senal_regulatoria": signal, "tecnologias": technologies, "bandas_frecuencia": bands,
        "paises_regiones": parse_list_field(row.get("paises", [])), "organizaciones": parse_list_field(row.get("organizaciones", [])), "actores": parse_list_field(row.get("actores", [])),
        "tipo_evento_regulatorio": infer_tipo_evento_regulatorio(" ".join([signal, _text(row, "resumen"), " ".join(keywords)])), "tipo_insumo_agenda": input_type,
        "relevancia_agenda_ane": _text(row, "relevancia_agenda_ane"), "evidencia_breve": "; ".join(evidence) + ".",
    }
    score, label = calculate_relevance_score(pd.Series(record))
    record.update(relevancia_score=score, relevancia_label=label, actividad_internacional_score=calculate_activity_score(pd.Series(record)))
    record["prioridad_score"] = score + record["actividad_internacional_score"]
    record["justificacion_analitica"] = _text(row, "justificacion_relevancia") or f"El tema {topic} aporta a {line} como insumo de {input_type.lower()}."
    record.pop("relevancia_agenda_ane")
    return record

def _write_counts(records: pd.DataFrame, column: str, label: str, path: Path, is_list: bool = False) -> None:
    values = records[column].map(parse_list_field).explode() if is_list else records[column]
    values.dropna().loc[lambda s: s.astype(str).str.len() > 0].value_counts().rename_axis(label).reset_index(name="count").to_csv(path, index=False, encoding="utf-8-sig")

def _write_matrix(records: pd.DataFrame, row_col: str, col_col: str, path: Path, row_list: bool = False, col_list: bool = False) -> None:
    pairs = records[[row_col, col_col]].copy()
    if row_list: pairs = pairs.assign(**{row_col: pairs[row_col].map(parse_list_field)}).explode(row_col)
    if col_list: pairs = pairs.assign(**{col_col: pairs[col_col].map(parse_list_field)}).explode(col_col)
    pairs = pairs.dropna().reset_index(drop=True)
    pd.crosstab(pairs[row_col], pairs[col_col]).reset_index().to_csv(path, index=False, encoding="utf-8-sig")

def _unique_join(series: pd.Series, lists: bool = False) -> str:
    values: list[str] = []
    for value in series:
        candidates = parse_list_field(value) if lists else [str(value).strip()]
        values.extend(item for item in candidates if item and item not in values)
    return ", ".join(values)

def _build_signals(records: pd.DataFrame) -> pd.DataFrame:
    keys = ["senal_regulatoria", "tema_estrategico", "linea_pmge", "tipo_insumo_agenda", "relevancia_label"]
    signals = records.groupby(keys, dropna=False).agg(num_documentos=("document_id", "nunique"), num_fuentes=("source_folder", "nunique"), fuentes=("source_folder", _unique_join), tecnologias=("tecnologias", lambda s: _unique_join(s, True)), bandas_frecuencia=("bandas_frecuencia", lambda s: _unique_join(s, True)), evidencia=("evidencia_breve", _unique_join), relevancia_score_promedio=("relevancia_score", "mean"), actividad_score_promedio=("actividad_internacional_score", "mean")).reset_index()
    signals["prioridad_score"] = (signals["relevancia_score_promedio"] + signals["actividad_score_promedio"]).round(2)
    return signals.sort_values("prioridad_score", ascending=False)

def build_dashboard_data() -> dict[str, Any]:
    if not INPUT_CSV.exists(): raise FileNotFoundError(f"No existe {INPUT_CSV}. Primero ejecute: python app/llm_extract.py")
    STRUCTURED_DATA_DIR.mkdir(parents=True, exist_ok=True); DEMO_DATA_DIR.mkdir(parents=True, exist_ok=True)
    source = pd.read_csv(INPUT_CSV, dtype=str, keep_default_na=False)
    records = pd.DataFrame([_make_record(row) for _, row in source.iterrows()])
    serializable = records.copy()
    for column in ["tecnologias", "bandas_frecuencia", "paises_regiones", "organizaciones", "actores", "tipo_evento_regulatorio"]:
        serializable[column] = serializable[column].map(lambda x: json.dumps(parse_list_field(x), ensure_ascii=False))
    serializable.to_csv(STRUCTURED_DATA_DIR / OUTPUT_NAMES[0], index=False, encoding="utf-8-sig")
    _write_counts(records, "tema_estrategico", "tema_estrategico", STRUCTURED_DATA_DIR / OUTPUT_NAMES[2]); _write_counts(records, "relevancia_label", "relevancia_label", STRUCTURED_DATA_DIR / OUTPUT_NAMES[3]); _write_counts(records, "tipo_insumo_agenda", "tipo_insumo_agenda", STRUCTURED_DATA_DIR / OUTPUT_NAMES[4]); _write_counts(records, "tecnologias", "tecnologia", STRUCTURED_DATA_DIR / OUTPUT_NAMES[5], True); _write_counts(records, "bandas_frecuencia", "banda_frecuencia", STRUCTURED_DATA_DIR / OUTPUT_NAMES[6], True)
    matrices = [("tema_estrategico", "source_folder", OUTPUT_NAMES[7], False, False), ("tema_estrategico", "tecnologias", OUTPUT_NAMES[8], False, True), ("bandas_frecuencia", "tecnologias", OUTPUT_NAMES[9], True, True), ("tema_estrategico", "tipo_insumo_agenda", OUTPUT_NAMES[10], False, False), ("tema_estrategico", "relevancia_label", OUTPUT_NAMES[11], False, False)]
    for row_col, col_col, name, row_list, col_list in matrices: _write_matrix(records, row_col, col_col, STRUCTURED_DATA_DIR / name, row_list, col_list)
    signals = _build_signals(records); signals.to_csv(STRUCTURED_DATA_DIR / OUTPUT_NAMES[1], index=False, encoding="utf-8-sig")
    for name in OUTPUT_NAMES: shutil.copy2(STRUCTURED_DATA_DIR / name, DEMO_DATA_DIR / name)
    return {"records_processed": len(records), "strategic_topics": records["tema_estrategico"].nunique(), "signals_generated": len(signals), "files_copied": len(OUTPUT_NAMES), "demo_data_dir": DEMO_DATA_DIR}

def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = build_dashboard_data()
    print(f"Registros procesados: {result['records_processed']}"); print(f"Temas estratégicos identificados: {result['strategic_topics']}"); print(f"Señales generadas: {result['signals_generated']}"); print(f"Archivos copiados a demo_data: {result['files_copied']}"); print(f"Ruta de demo_data: {result['demo_data_dir']}")

if __name__ == "__main__": main()
