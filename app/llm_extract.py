"""Extracción estructurada del corpus mediante un proveedor LLM."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm

# Permite ``python app/llm_extract.py`` además de ``python -m app.llm_extract``.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    LLM_PROVIDER,
    LOGS_DIR,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    PROJECT_ROOT,
    STRUCTURED_DATA_DIR,
)


INPUT_CSV = STRUCTURED_DATA_DIR / "document_texts.csv"
PARTIAL_CSV = STRUCTURED_DATA_DIR / "structured_documents_partial.csv"
FINAL_CSV = STRUCTURED_DATA_DIR / "structured_documents.csv"
PROMPT_PATH = PROJECT_ROOT / "prompts" / "extraction_prompt.txt"

LIST_FIELDS = [
    "temas_secundarios",
    "tecnologias",
    "bandas_frecuencia",
    "paises",
    "organizaciones",
    "actores",
    "palabras_clave",
]
TEXT_FIELDS = [
    "tema_principal",
    "tipo_documento",
    "resumen",
    "relevancia_agenda_ane",
    "justificacion_relevancia",
]
ALLOWED_RELEVANCE = {"", "Alta", "Media", "Baja"}

OUTPUT_COLUMNS = [
    "document_id",
    "file_name",
    "source_folder",
    "file_type",
    "tema_principal",
    "temas_secundarios",
    "tecnologias",
    "bandas_frecuencia",
    "paises",
    "organizaciones",
    "actores",
    "tipo_documento",
    "palabras_clave",
    "resumen",
    "relevancia_agenda_ane",
    "justificacion_relevancia",
    "llm_status",
    "llm_error",
]


def _configure_logging() -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("llm_extraction")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    handler = logging.FileHandler(
        LOGS_DIR / "llm_extraction.log", mode="w", encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    )
    logger.addHandler(handler)
    return logger


def _create_openai_client(api_key: str) -> Any:
    """Crea el cliente de forma diferida para facilitar cambios de proveedor."""
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "No está instalado el paquete 'openai'. Ejecute "
            "'python -m pip install -r requirements.txt'."
        ) from exc
    return OpenAI(api_key=api_key)


def _call_gemini(full_prompt: str) -> str:
    """Realiza una llamada JSON a Gemini con el SDK oficial de Google."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "No está instalado el paquete 'google-genai'. Ejecute "
            "'python -m pip install -r requirements.txt'."
        ) from exc

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=full_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return response.text


def _call_openai(full_prompt: str) -> str:
    """Realiza una llamada mediante Responses API de OpenAI."""
    client = _create_openai_client(OPENAI_API_KEY)
    response = client.responses.create(model=OPENAI_MODEL, input=full_prompt)
    return response.output_text


def _load_inputs() -> tuple[pd.DataFrame, str]:
    if not INPUT_CSV.is_file():
        raise FileNotFoundError(
            f"No se encontró {INPUT_CSV}. Ejecute primero build_dataset.py."
        )
    if not PROMPT_PATH.is_file():
        raise FileNotFoundError(f"No se encontró el prompt: {PROMPT_PATH}")

    dataframe = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
    required = {
        "document_id",
        "file_name",
        "source_folder",
        "file_type",
        "text",
        "status",
    }
    missing = required.difference(dataframe.columns)
    if missing:
        raise ValueError(
            "Faltan columnas requeridas en document_texts.csv: "
            + ", ".join(sorted(missing))
        )

    dataframe = dataframe.copy()
    for column in required:
        dataframe[column] = dataframe[column].fillna("").astype(str)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"El prompt está vacío: {PROMPT_PATH}")
    return dataframe, prompt


def _empty_extraction() -> dict[str, Any]:
    return {
        "tema_principal": "",
        "temas_secundarios": [],
        "tecnologias": [],
        "bandas_frecuencia": [],
        "paises": [],
        "organizaciones": [],
        "actores": [],
        "tipo_documento": "",
        "palabras_clave": [],
        "resumen": "",
        "relevancia_agenda_ane": "",
        "justificacion_relevancia": "",
    }


def _validate_response(raw_response: str) -> dict[str, Any]:
    """Decodifica el JSON y valida tipos y valores básicos del contrato."""
    parsed = json.loads(raw_response)
    if not isinstance(parsed, dict):
        raise ValueError("La respuesta JSON debe ser un objeto.")

    validated = _empty_extraction()
    for field in TEXT_FIELDS:
        value = parsed.get(field, "")
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise ValueError(f"El campo '{field}' debe ser texto.")
        validated[field] = value.strip()

    for field in LIST_FIELDS:
        value = parsed.get(field, [])
        if value is None:
            value = []
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            raise ValueError(f"El campo '{field}' debe ser una lista de textos.")
        validated[field] = [item.strip() for item in value if item.strip()]

    relevance = validated["relevancia_agenda_ane"]
    if relevance not in ALLOWED_RELEVANCE:
        raise ValueError(
            "'relevancia_agenda_ane' debe estar vacía o ser Alta, Media o Baja."
        )
    return validated


def call_llm(prompt: str, document_text: str) -> dict:
    """Llama al proveedor configurado y devuelve una extracción validada."""
    full_prompt = f"{prompt.rstrip()}\n\nTEXTO DEL DOCUMENTO:\n{document_text}"
    provider = LLM_PROVIDER.strip().lower()

    if provider == "gemini":
        raw_response = _call_gemini(full_prompt)
    elif provider == "openai":
        raw_response = _call_openai(full_prompt)
    else:
        raise ValueError(f"Proveedor LLM no soportado: '{LLM_PROVIDER}'.")

    if not raw_response or not raw_response.strip():
        raise ValueError("El LLM devolvió una respuesta vacía.")
    return _validate_response(raw_response)


def _prompt_with_metadata(prompt: str, metadata: dict[str, str]) -> str:
    """Añade al prompt los metadatos disponibles del documento."""
    return (
        f"{prompt.rstrip()}\n\n"
        "METADATOS DEL DOCUMENTO:\n"
        f"- file_name: {metadata['file_name']}\n"
        f"- source_folder: {metadata['source_folder']}\n"
        f"- file_type: {metadata['file_type']}"
    )


def _serialize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Serializa listas como JSON para conservar una representación estable."""
    serialized = record.copy()
    for field in LIST_FIELDS:
        serialized[field] = json.dumps(
            serialized.get(field, []), ensure_ascii=False
        )
    return serialized


def _save_results(records: list[dict[str, Any]], output_path: Path) -> pd.DataFrame:
    dataframe = pd.DataFrame(
        [_serialize_record(record) for record in records], columns=OUTPUT_COLUMNS
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")
    return dataframe


def run_llm_extraction(
    limit: int | None = 20,
    max_chars: int = 12000,
) -> pd.DataFrame:
    """Extrae campos estructurados de las filas válidas del corpus.

    No se realiza ninguna llamada si falta la clave API. ``limit=None`` permite
    procesar todas las filas válidas de forma explícita.
    """
    if limit is not None and limit < 0:
        raise ValueError("limit debe ser un entero no negativo o None.")
    if max_chars <= 0:
        raise ValueError("max_chars debe ser mayor que cero.")

    logger = _configure_logging()
    provider = LLM_PROVIDER.strip().lower()

    if provider not in {"gemini", "openai"}:
        message = (
            f"Proveedor LLM no soportado: '{LLM_PROVIDER}'. "
            "Use LLM_PROVIDER=gemini o LLM_PROVIDER=openai."
        )
        print(message)
        logger.error(message)
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    if provider == "gemini" and not GEMINI_API_KEY.strip():
        message = (
            "No se encontró GEMINI_API_KEY en .env. Configura la clave antes "
            "de ejecutar la extracción LLM."
        )
        print(message)
        logger.warning(message)
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    if provider == "openai" and not OPENAI_API_KEY.strip():
        message = (
            "OPENAI_API_KEY no está configurada. No se realizó ninguna llamada "
            "al LLM ni se generaron costos. Configure la clave en el archivo .env."
        )
        print(message)
        logger.warning(message)
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    dataframe, prompt = _load_inputs()
    candidates = dataframe.loc[dataframe["status"].str.lower() == "ok"].copy()
    if limit is not None:
        candidates = candidates.head(limit)

    logger.info(
        "Inicio. provider=%s | model=%s | documentos=%d | max_chars=%d",
        provider,
        GEMINI_MODEL if provider == "gemini" else OPENAI_MODEL,
        len(candidates),
        max_chars,
    )
    records: list[dict[str, Any]] = []

    for row in tqdm(
        candidates.itertuples(index=False),
        total=len(candidates),
        desc="Extracción con LLM",
        unit="documento",
    ):
        metadata = {
            "document_id": row.document_id,
            "file_name": row.file_name,
            "source_folder": row.source_folder,
            "file_type": row.file_type,
        }
        try:
            extraction = call_llm(
                prompt=_prompt_with_metadata(prompt, metadata),
                document_text=row.text[:max_chars],
            )
            record = {
                **metadata,
                **extraction,
                "llm_status": "ok",
                "llm_error": "",
            }
            logger.info("Procesado correctamente: %s", row.document_id)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            record = {
                **metadata,
                **_empty_extraction(),
                "llm_status": "error",
                "llm_error": error,
            }
            logger.error("Error en %s | %s", row.document_id, error)

        records.append(record)
        _save_results(records, PARTIAL_CSV)

    result = _save_results(records, FINAL_CSV)
    errors = int((result["llm_status"] == "error").sum()) if not result.empty else 0
    logger.info("Fin. procesados=%d | errores=%d | salida=%s", len(result), errors, FINAL_CSV)

    print("\nExtracción estructurada finalizada")
    print(f"- Documentos procesados: {len(result)}")
    print(f"- Errores: {errors}")
    print(f"- Archivo final: {FINAL_CSV}")
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Define y procesa los argumentos de la interfaz de consola."""
    parser = argparse.ArgumentParser(
        description="Extrae información estructurada del corpus mediante el LLM configurado."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Número máximo de documentos por procesar (predeterminado: 20).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=12000,
        help="Máximo de caracteres enviados por documento (predeterminado: 12000).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> pd.DataFrame:
    """Punto de entrada para la ejecución desde consola."""
    args = _parse_args(argv)
    return run_llm_extraction(limit=args.limit, max_chars=args.max_chars)


if __name__ == "__main__":
    main()
