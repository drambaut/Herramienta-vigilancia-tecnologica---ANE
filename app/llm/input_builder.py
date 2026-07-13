"""Constructores de entradas LLM para documentos preparados."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.documents.models import DocumentChunk
from app.llm.base import LLMInput


def build_pdf_input(
    *,
    file_name: str,
    file_bytes: bytes,
    metadata: Mapping[str, str] | None = None,
) -> LLMInput:
    """Construye entrada PDF conservando los bytes originales."""
    return LLMInput(
        text="Analiza el PDF original adjunto usando estos metadatos como contexto.",
        file_bytes=file_bytes,
        mime_type="application/pdf",
        file_name=file_name,
        metadata=dict(metadata or {}),
    )


def build_excel_input(
    *,
    file_name: str,
    chunks: Iterable[DocumentChunk],
    metadata: Mapping[str, str] | None = None,
) -> LLMInput:
    """Construye entrada textual estructurada desde chunks Excel."""
    ordered_chunks = sorted(chunks, key=lambda chunk: chunk.position)
    lines = [
        f"ARCHIVO: {file_name}",
        "CONTENIDO ESTRUCTURADO POR HOJAS Y FILAS",
    ]
    current_sheet: str | None = None
    for chunk in ordered_chunks:
        sheet_name = chunk.sheet_name or ""
        if sheet_name != current_sheet:
            lines.append("")
            lines.append(f"=== SHEET: {sheet_name} ===")
            current_sheet = sheet_name
        lines.extend(
            [
                f"ROW_REFERENCE: {chunk.row_reference or ''}",
                "CONTENT:",
                chunk.content,
                "---",
            ]
        )

    return LLMInput(
        text="\n".join(lines).strip(),
        file_bytes=None,
        mime_type=None,
        file_name=file_name,
        metadata=dict(metadata or {}),
    )
