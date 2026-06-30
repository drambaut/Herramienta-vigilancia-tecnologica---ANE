"""Pruebas de extracción LLM sin llamadas externas ni costos."""

import json
from pathlib import Path

import pandas as pd

import app.llm_extract as llm_module


VALID_EXTRACTION = {
    "tema_principal": "Gestión del espectro",
    "temas_secundarios": ["Monitoreo"],
    "tecnologias": ["5G"],
    "bandas_frecuencia": ["3.5 GHz"],
    "paises": ["Colombia"],
    "organizaciones": ["ANE"],
    "actores": ["Reguladores"],
    "tipo_documento": "Informe",
    "palabras_clave": ["espectro"],
    "resumen": "Resumen de prueba.",
    "relevancia_agenda_ane": "Alta",
    "justificacion_relevancia": "Apoya la planeación del espectro.",
}


def _input_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "document_id": "doc-1",
                "file_name": "uno.pdf",
                "source_folder": "Fuente",
                "file_type": "pdf",
                "text": "A" * 100,
                "status": "ok",
            },
            {
                "document_id": "doc-2",
                "file_name": "dos.pdf",
                "source_folder": "Fuente",
                "file_type": "pdf",
                "text": "Texto dos",
                "status": "ok",
            },
            {
                "document_id": "doc-3",
                "file_name": "error.pdf",
                "source_folder": "Fuente",
                "file_type": "pdf",
                "text": "No debe procesarse",
                "status": "error",
            },
        ]
    )


def _patch_paths(tmp_path: Path, monkeypatch) -> None:
    structured = tmp_path / "structured"
    logs = tmp_path / "logs"
    prompt = tmp_path / "prompt.txt"
    structured.mkdir()
    prompt.write_text("Devuelve únicamente JSON.", encoding="utf-8")
    _input_dataframe().to_csv(structured / "document_texts.csv", index=False)

    monkeypatch.setattr(llm_module, "INPUT_CSV", structured / "document_texts.csv")
    monkeypatch.setattr(llm_module, "PARTIAL_CSV", structured / "partial.csv")
    monkeypatch.setattr(llm_module, "FINAL_CSV", structured / "final.csv")
    monkeypatch.setattr(llm_module, "PROMPT_PATH", prompt)
    monkeypatch.setattr(llm_module, "LOGS_DIR", logs)


def test_missing_gemini_key_stops_without_creating_results(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    _patch_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(llm_module, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(llm_module, "GEMINI_API_KEY", "")

    result = llm_module.run_llm_extraction()

    assert result.empty
    assert not llm_module.FINAL_CSV.exists()
    assert "No se encontró GEMINI_API_KEY en .env" in capsys.readouterr().out


def test_extraction_saves_success_and_error_incrementally(
    tmp_path: Path, monkeypatch
) -> None:
    _patch_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(llm_module, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(llm_module, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(llm_module, "GEMINI_MODEL", "test-model")
    calls: list[tuple[str, str]] = []
    outputs = iter([VALID_EXTRACTION, ValueError("JSONDecodeError simulado")])

    def fake_call_llm(prompt: str, document_text: str) -> dict:
        calls.append((prompt, document_text))
        output = next(outputs)
        if isinstance(output, Exception):
            raise output
        return output

    monkeypatch.setattr(llm_module, "call_llm", fake_call_llm)

    result = llm_module.run_llm_extraction(limit=2, max_chars=12)

    assert list(result["llm_status"]) == ["ok", "error"]
    assert len(calls[0][1]) == 12
    assert "file_name: uno.pdf" in calls[0][0]
    assert "source_folder: Fuente" in calls[0][0]
    assert "file_type: pdf" in calls[0][0]
    assert llm_module.PARTIAL_CSV.is_file()
    assert llm_module.FINAL_CSV.is_file()
    assert json.loads(result.iloc[0]["tecnologias"]) == ["5G"]
    assert "JSONDecodeError" in result.iloc[1]["llm_error"]


def test_call_llm_routes_to_gemini_and_combines_prompt(monkeypatch) -> None:
    monkeypatch.setattr(llm_module, "LLM_PROVIDER", "gemini")
    captured: list[str] = []

    def fake_gemini(full_prompt: str) -> str:
        captured.append(full_prompt)
        return json.dumps(VALID_EXTRACTION)

    monkeypatch.setattr(llm_module, "_call_gemini", fake_gemini)

    result = llm_module.call_llm("Instrucciones", "Contenido documental")

    assert result["tema_principal"] == "Gestión del espectro"
    assert "Instrucciones" in captured[0]
    assert "Contenido documental" in captured[0]


def test_call_llm_keeps_openai_compatibility(monkeypatch) -> None:
    monkeypatch.setattr(llm_module, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(
        llm_module, "_call_openai", lambda full_prompt: json.dumps(VALID_EXTRACTION)
    )

    result = llm_module.call_llm("Prompt", "Texto")

    assert result["relevancia_agenda_ane"] == "Alta"


def test_invalid_relevance_is_rejected() -> None:
    invalid = {**VALID_EXTRACTION, "relevancia_agenda_ane": "Muy alta"}

    try:
        llm_module._validate_response(json.dumps(invalid))
    except ValueError as exc:
        assert "Alta, Media o Baja" in str(exc)
    else:
        raise AssertionError("La relevancia inválida debió rechazarse")


def test_cli_arguments_keep_defaults() -> None:
    args = llm_module._parse_args([])

    assert args.limit == 20
    assert args.max_chars == 12000


def test_cli_arguments_accept_custom_values() -> None:
    args = llm_module._parse_args(["--limit", "50", "--max-chars", "9000"])

    assert args.limit == 50
    assert args.max_chars == 9000
