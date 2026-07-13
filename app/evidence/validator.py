"""Validador de evidencias contra chunks tecnicos."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from app.documents.models import Document, DocumentChunk
from app.evidence.models import (
    EvidenceValidationItem,
    EvidenceValidationReport,
    EvidenceValidationStatus,
)


class EvidenceValidator:
    """Comprueba citas literales contra chunks preparados."""

    def validate(
        self,
        document: Document,
        chunks: Sequence[DocumentChunk],
        payload: dict,
    ) -> EvidenceValidationReport:
        evidence_entries = payload.get("evidence", [])
        evidence_by_id: dict[str, dict] = {}
        duplicate_ids: set[str] = set()
        for evidence in evidence_entries:
            evidence_id = str(evidence.get("temporary_id", ""))
            if evidence_id in evidence_by_id:
                duplicate_ids.add(evidence_id)
            else:
                evidence_by_id[evidence_id] = evidence

        referenced_ids = self._collect_evidence_ids(payload)
        items: list[EvidenceValidationItem] = []

        for evidence_id in sorted(duplicate_ids):
            items.append(
                EvidenceValidationItem(
                    evidence_id=evidence_id,
                    status=EvidenceValidationStatus.DUPLICATE_ID,
                    matched_chunk_id=None,
                    message=f"temporary_id duplicado: {evidence_id}.",
                    page_number=None,
                    sheet_name=None,
                    row_reference=None,
                )
            )

        for evidence_id in referenced_ids:
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                items.append(
                    EvidenceValidationItem(
                        evidence_id=evidence_id,
                        status=EvidenceValidationStatus.MISSING_REFERENCE,
                        matched_chunk_id=None,
                        message=f"evidence_id inexistente: {evidence_id}.",
                        page_number=None,
                        sheet_name=None,
                        row_reference=None,
                    )
                )
                continue
            items.append(self._validate_evidence(evidence, chunks))

        verified_count = sum(
            item.status == EvidenceValidationStatus.VERIFIED for item in items
        )
        invalid_count = len(items) - verified_count
        return EvidenceValidationReport(
            document_id=document.id,
            items=items,
            total=len(items),
            verified_count=verified_count,
            invalid_count=invalid_count,
            is_valid=invalid_count == 0,
        )

    def _validate_evidence(
        self, evidence: dict, chunks: Sequence[DocumentChunk]
    ) -> EvidenceValidationItem:
        evidence_id = str(evidence.get("temporary_id", ""))
        quote = str(evidence.get("quote") or "")
        if not quote.strip():
            return self._item(
                evidence_id,
                EvidenceValidationStatus.NOT_FOUND,
                "quote vacio.",
                evidence,
            )

        page_number = evidence.get("page_number")
        sheet_name = evidence.get("sheet_name")
        row_reference = evidence.get("row_reference")

        if sheet_name is not None or row_reference is not None:
            return self._validate_excel_location(evidence, chunks, quote)
        if page_number is not None:
            return self._validate_pdf_location(evidence, chunks, quote)
        return self._validate_without_location(evidence, chunks, quote)

    def _validate_pdf_location(
        self, evidence: dict, chunks: Sequence[DocumentChunk], quote: str
    ) -> EvidenceValidationItem:
        page_number = evidence.get("page_number")
        page_chunks = [chunk for chunk in chunks if chunk.page_number == page_number]
        match = self._first_match(page_chunks, quote)
        if match is not None:
            return self._verified(evidence, match)
        if self._first_match(chunks, quote) is not None:
            return self._item(
                evidence["temporary_id"],
                EvidenceValidationStatus.INVALID_LOCATION,
                "La cita existe, pero no en la pagina declarada.",
                evidence,
            )
        return self._item(
            evidence["temporary_id"],
            EvidenceValidationStatus.NOT_FOUND,
            "La cita no aparece en los chunks del documento.",
            evidence,
        )

    def _validate_excel_location(
        self, evidence: dict, chunks: Sequence[DocumentChunk], quote: str
    ) -> EvidenceValidationItem:
        sheet_name = evidence.get("sheet_name")
        row_reference = evidence.get("row_reference")
        if not sheet_name or not row_reference:
            return self._validate_without_location(evidence, chunks, quote)

        location_chunks = [
            chunk
            for chunk in chunks
            if chunk.sheet_name == sheet_name and chunk.row_reference == row_reference
        ]
        match = self._first_match(location_chunks, quote)
        if match is not None:
            return self._verified(evidence, match)
        if self._first_match(chunks, quote) is not None:
            return self._item(
                evidence["temporary_id"],
                EvidenceValidationStatus.INVALID_LOCATION,
                "La cita existe, pero no en la hoja/fila declarada.",
                evidence,
            )
        return self._item(
            evidence["temporary_id"],
            EvidenceValidationStatus.NOT_FOUND,
            "La cita no aparece en los chunks del documento.",
            evidence,
        )

    def _validate_without_location(
        self, evidence: dict, chunks: Sequence[DocumentChunk], quote: str
    ) -> EvidenceValidationItem:
        matches = [chunk for chunk in chunks if self._contains(chunk.content, quote)]
        if len(matches) == 1:
            return self._verified(evidence, matches[0])
        if len(matches) > 1:
            return self._item(
                evidence["temporary_id"],
                EvidenceValidationStatus.INVALID_LOCATION,
                "La cita aparece en multiples chunks; falta ubicacion precisa.",
                evidence,
            )
        return self._item(
            evidence["temporary_id"],
            EvidenceValidationStatus.NOT_FOUND,
            "La cita no aparece en los chunks del documento.",
            evidence,
        )

    def _verified(self, evidence: dict, chunk: DocumentChunk) -> EvidenceValidationItem:
        return EvidenceValidationItem(
            evidence_id=evidence["temporary_id"],
            status=EvidenceValidationStatus.VERIFIED,
            matched_chunk_id=chunk.id,
            message="Evidencia verificada.",
            page_number=chunk.page_number,
            sheet_name=chunk.sheet_name,
            row_reference=chunk.row_reference,
        )

    def _item(
        self,
        evidence_id: str,
        status: EvidenceValidationStatus,
        message: str,
        evidence: dict,
    ) -> EvidenceValidationItem:
        return EvidenceValidationItem(
            evidence_id=evidence_id,
            status=status,
            matched_chunk_id=None,
            message=message,
            page_number=evidence.get("page_number"),
            sheet_name=evidence.get("sheet_name"),
            row_reference=evidence.get("row_reference"),
        )

    def _first_match(
        self, chunks: Sequence[DocumentChunk], quote: str
    ) -> DocumentChunk | None:
        for chunk in chunks:
            if self._contains(chunk.content, quote):
                return chunk
        return None

    def _contains(self, content: str, quote: str) -> bool:
        return self._normalize(quote) in self._normalize(content)

    def _normalize(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip().casefold()

    def _collect_evidence_ids(self, value) -> list[str]:
        found: list[str] = []
        self._walk_evidence_ids(value, found)
        return found

    def _walk_evidence_ids(self, value, found: list[str]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "evidence_ids" and isinstance(child, list):
                    found.extend(str(item) for item in child)
                else:
                    self._walk_evidence_ids(child, found)
        elif isinstance(value, list):
            for item in value:
                self._walk_evidence_ids(item, found)
