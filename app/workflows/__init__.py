"""Workflows de la nueva arquitectura modular."""

from app.workflows.document_analysis import (
    DocumentAnalysisWorkflow,
    DocumentAnalysisWorkflowResult,
)
from app.workflows.errors import WorkflowError

__all__ = [
    "DocumentAnalysisWorkflow",
    "DocumentAnalysisWorkflowResult",
    "WorkflowError",
]
