"""Top-level entry point: turn an uploaded image into a 9x9 Sudoku grid.

The pipeline is:

``bytes -> preprocess -> grid detection -> perspective correction -> cells ->
digit classification -> validation``

Only the ``sudoku.utils.validation`` module is imported from the rest of the
project, so this package stays free of Django and of the solver algorithms.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sudoku.utils.validation import SudokuValidationError, validate_grid

from . import grid_detection, preprocessing
from .digit_recognition import recognize_digits


class SudokuExtractionError(Exception):
    """Raised when an image cannot be turned into a grid.

    ``code`` is a stable machine-readable identifier and ``status`` the HTTP
    status the API view should return.
    """

    def __init__(self, message: str, code: str = "extraction_failed", status: int = 422):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _warn_if_weak(result: Dict[str, Any]) -> None:
    """Attach human-readable warnings to a successful recognition."""
    grid: List[List[int]] = result["grid"]
    recognised = result["recognized_cells"]
    warnings: List[str] = []

    if recognised < 17:
        warnings.append(
            "Only a few digits were recognised. Check every cell before solving."
        )
    if recognised == 0:
        warnings.append("No digits were recognised in the detected grid.")

    low_confidence = sum(
        1
        for row_index, row in enumerate(grid)
        for col_index, value in enumerate(row)
        if value and result["cell_confidence"][row_index][col_index] < 0.6
    )
    if low_confidence:
        warnings.append(
            f"{low_confidence} cell(s) were recognised with low confidence and are "
            "highlighted for review."
        )
    result["warnings"] = warnings


def extract_sudoku_from_image(image_bytes: bytes) -> Dict[str, Any]:
    """Run the full recognition pipeline.

    Returns a dictionary with ``status``, ``grid``, ``recognized_cells``,
    ``empty_cells``, ``confidence``, ``cell_confidence``, ``warnings`` and
    ``message``. Raises :class:`SudokuExtractionError` on any failure.
    """
    if not image_bytes:
        raise SudokuExtractionError(
            "No image was uploaded.", code="missing_image", status=400
        )

    try:
        loaded = preprocessing.preprocess(image_bytes)
    except preprocessing.ImageDecodeError as exc:
        raise SudokuExtractionError(
            str(exc), code="invalid_image", status=422
        ) from exc

    board = grid_detection.extract_board(loaded.binary, side=450)
    if board is None:
        raise SudokuExtractionError(
            "No Sudoku grid was found in the image. Try a clearer, more "
            "cropped picture of the board.",
            code="no_grid_detected",
            status=422,
        )

    try:
        grid, cell_confidence = recognize_digits(board)
    except (ValueError, SudokuExtractionError):
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise SudokuExtractionError(
            "The grid was detected but the cells could not be read.",
            code="cell_recognition_failed",
            status=422,
        ) from exc

    recognised_cells = sum(1 for row in grid for value in row if value)
    empty_cells = 81 - recognised_cells
    if recognised_cells == 0:
        raise SudokuExtractionError(
            "The grid was detected but no digits could be read. Try a "
            "higher-resolution image.",
            code="cell_recognition_failed",
            status=422,
        )

    scores = [
        cell_confidence[r][c]
        for r in range(9)
        for c in range(9)
        if grid[r][c]
    ]
    confidence = float(sum(scores) / len(scores)) if scores else 0.0

    conflict: str | None = None
    try:
        validate_grid(grid)
    except SudokuValidationError as exc:
        conflict = str(exc)

    result: Dict[str, Any] = {
        "status": "conflicts" if conflict else "ok",
        "grid": grid,
        "recognized_cells": recognised_cells,
        "empty_cells": empty_cells,
        "confidence": round(confidence, 3),
        "cell_confidence": [
            [round(value, 3) for value in row] for row in cell_confidence
        ],
        "warnings": [],
        "message": (
            "Sudoku grid extracted successfully."
            if not conflict
            else "The puzzle was extracted, but some recognised digits conflict."
        ),
    }
    if conflict:
        result["conflict"] = conflict
    _warn_if_weak(result)
    if conflict:
        result["warnings"].append(conflict)
        result["warnings"].append(
            "Conflicting clues were left exactly as recognised; correct them "
            "on the board before solving."
        )
    return result
