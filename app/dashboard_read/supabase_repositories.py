"""Repositorios Supabase de solo lectura para el dashboard publicado."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Callable

from app.core.settings import Settings
from app.documents.models import Document
from app.documents.supabase_repository import SupabaseDocumentRepository
from app.results.models import PersistenceBundle
from app.results.supabase_repository import SupabaseResultRepository


class SupabaseDashboardDocumentReadRepository:
    """Lectura de documentos via `SupabaseDocumentRepository`."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        client_factory: Callable[[str, str], Any] | None = None,
        document_repository: SupabaseDocumentRepository | None = None,
    ) -> None:
        self._documents = document_repository or SupabaseDocumentRepository(
            settings=settings,
            client=client,
            client_factory=client_factory,
        )

    def get_documents_by_ids(self, document_ids: Sequence[str]) -> list[Document]:
        documents: list[Document] = []
        for document_id in document_ids:
            document = self._documents.get_document(document_id)
            if document is not None:
                documents.append(document)
        return documents


class SupabaseDashboardResultReadRepository:
    """Lectura de bundles via `SupabaseResultRepository`."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        client: Any | None = None,
        client_factory: Callable[[str, str], Any] | None = None,
        result_repository: SupabaseResultRepository | None = None,
    ) -> None:
        self._results = result_repository or SupabaseResultRepository(
            settings=settings,
            client=client,
            client_factory=client_factory,
        )

    def get_bundles_by_document_ids(
        self, document_ids: Sequence[str]
    ) -> list[PersistenceBundle]:
        bundles: list[PersistenceBundle] = []
        for document_id in document_ids:
            bundle = self._results.get_bundle(document_id)
            if bundle is not None:
                bundles.append(bundle)
        return bundles
