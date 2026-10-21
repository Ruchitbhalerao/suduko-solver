"""Constraint primitives for the Sudoku AI engine.

This module is intentionally free of any Django (and third-party) dependency so
the AI engine can be imported, tested, and reused on its own.

Internal representation
-----------------------
* A grid is a list of exactly ``GRID_SIZE`` rows.
* Every row contains exactly ``GRID_SIZE`` cells.
* ``EMPTY_CELL`` (``0``) marks an empty cell.
* Integers ``1``..``9`` mark filled cells.

Indices are zero-based. Only the explicit scalar arguments (``row``, ``col``,
``value``) are validated here, and malformed arguments raise ``ValueError``
with a clear message. Callers are expected to pass a structurally valid grid;
rich, user-facing grid validation lives in ``sudoku.utils.validation``.

None of these functions mutate the grid they are given.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

Grid = List[List[int]]

GRID_SIZE = 9
BOX_SIZE = 3
EMPTY_CELL = 0
MIN_VALUE = 1
MAX_VALUE = 9


def _is_plain_int(value: object) -> bool:
    """Return True for real integers only, rejecting ``bool``.

    ``bool`` subclasses ``int`` in Python, so ``isinstance(True, int)`` is True.
    A boolean is never a meaningful Sudoku value, so it is rejected explicitly.
    """
    return isinstance(value, int) and not isinstance(value, bool)


def _require_index(name: str, position: object) -> None:
    """Raise ``ValueError`` unless ``position`` is an integer in ``0..8``."""
    if not _is_plain_int(position):
        raise ValueError(
            f"{name} must be an integer, got {type(position).__name__}."
        )
    if not 0 <= position < GRID_SIZE:
        raise ValueError(
            f"{name} must be between 0 and {GRID_SIZE - 1}, got {position}."
        )


def _require_value(value: object) -> None:
    """Raise ``ValueError`` unless ``value`` is an integer in ``1..9``."""
    if not _is_plain_int(value):
        raise ValueError(f"value must be an integer, got {type(value).__name__}.")
    if not MIN_VALUE <= value <= MAX_VALUE:
        raise ValueError(
            f"value must be between {MIN_VALUE} and {MAX_VALUE}, got {value}. "
            f"{EMPTY_CELL} is never a valid Sudoku candidate."
        )


def _box_origin(position: int) -> int:
    """Return the first row/column index of the 3x3 box containing ``position``."""
    return (position // BOX_SIZE) * BOX_SIZE


def is_valid_move(grid: Grid, row: int, col: int, value: int) -> bool:
    """Return True if ``value`` may legally be placed at (``row``, ``col``).

    The cell's own current value is ignored, so querying a cell that already
    contains ``value`` returns True instead of falsely conflicting with itself.

    Raises ``ValueError`` for an out-of-range index or an illegal ``value``.
    """
    _require_index("row", row)
    _require_index("col", col)
    _require_value(value)

    if any(cell == value for index, cell in enumerate(grid[row]) if index != col):
        return False
    if any(grid[r][col] == value for r in range(GRID_SIZE) if r != row):
        return False

    top = _box_origin(row)
    left = _box_origin(col)
    for r in range(top, top + BOX_SIZE):
        for c in range(left, left + BOX_SIZE):
            if (r, c) != (row, col) and grid[r][c] == value:
                return False
    return True


def get_candidates(grid: Grid, row: int, col: int) -> List[int]:
    """Return the ascending list of legal values for the cell (``row``, ``col``).

    The result is deterministic, contains only unique values in ``1..9``, and
    never contains ``0``. Works for empty or already-filled cells (a filled cell
    reports the values that would be legal there if it were empty).

    Raises ``ValueError`` for an out-of-range index.
    """
    _require_index("row", row)
    _require_index("col", col)
    return [
        candidate
        for candidate in range(MIN_VALUE, MAX_VALUE + 1)
        if is_valid_move(grid, row, col, candidate)
    ]


def find_empty_cell(grid: Grid) -> Optional[Tuple[int, int]]:
    """Return the first empty cell in row-major order, or None if none remain.

    The first cell whose value is ``EMPTY_CELL`` (``0``) is returned as a
    ``(row, col)`` tuple of zero-based indices. Returns None for a full grid.
    """
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            if grid[row][col] == EMPTY_CELL:
                return (row, col)
    return None
