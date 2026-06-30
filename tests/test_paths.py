"""Pruebas básicas para la configuración de rutas."""

from pathlib import Path

from app.config import (
    DATA_DIR,
    EXTRACTED_TEXT_DIR,
    FIGURES_DIR,
    LOGS_DIR,
    OUTPUT_DIR,
    STRUCTURED_DATA_DIR,
)


def test_configured_paths_are_path_objects() -> None:
    paths = (
        DATA_DIR,
        OUTPUT_DIR,
        EXTRACTED_TEXT_DIR,
        STRUCTURED_DATA_DIR,
        FIGURES_DIR,
        LOGS_DIR,
    )
    assert all(isinstance(path, Path) for path in paths)


def test_output_directories_exist() -> None:
    output_directories = (
        OUTPUT_DIR,
        EXTRACTED_TEXT_DIR,
        STRUCTURED_DATA_DIR,
        FIGURES_DIR,
        LOGS_DIR,
    )
    assert all(directory.is_dir() for directory in output_directories)
