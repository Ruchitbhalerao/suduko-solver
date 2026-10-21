"""Input validation for Sudoku grids.

This module owns structural validation, clue validation, completeness checks,
and full solution verification. It depends only on the constraint primitives in
``sudoku.ai.constraints`` and the Python standard library -- never on Django.

Conventions
-----------
* Every ``validate_*`` function returns ``None`` on success and raises
  :class:`SudokuValidationError` (a subclass of ``ValueError``) with a
  human-readable message on the first problem found.
* The matching ``is_*`` helpers return a ``bool`` instead of raising.
* Error messages describe rows, columns, and subgrids using one-based numbering
  for readability, while every public API uses zero-based indices.

No function here mutates the grid it is given.
"""

from __future__ import annotations

from typing import List, Optional

from sudoku.ai.constraints import (
    BOX_SIZE,
    EMPTY_CELL,
    GRID_SIZE,
    MAX_VALUE,
    MIN_VALUE,
    is_valid_move,
)

Grid = List[List[int]]


class SudokuValidationError(ValueError):
    """Raised when a Sudoku grid is malformed or breaks a Sudoku rule."""


def _is_plain_int(value: object) -> bool:
    """Return True for real integers only, rejecting ``bool``."""
    return isinstance(value, int) and not isinstance(value, bool)


def validate_grid_structure(grid: object) -> None:
    """Raise :class:`SudokuValidationError` unless ``grid`` is a well-formed 9x9 grid.

    A well-formed grid is a list of exactly nine rows, each a list of exactly
    nine cells, where every cell is an integer (not a bool) in ``0..9``.
    """
    if not isinstance(grid, list):
        raise SudokuValidationError(
            f"Grid must be a list of rows, got {type(grid).__name__}."
        )
    if len(grid) != GRID_SIZE:
        raise SudokuValidationError(
            f"Grid must contain exactly {GRID_SIZE} rows, got {len(grid)}."
        )

    for row_index, row in enumerate(grid):
        if not isinstance(row, list):
            raise SudokuValidationError(
                f"Row {row_index + 1} must be a list, got {type(row).__name__}."
            )
        if len(row) != GRID_SIZE:
            raise SudokuValidationError(
                f"Row {row_index + 1} must contain exactly {GRID_SIZE} cells, "
                f"got {len(row)}."
            )
        for col_index, cell in enumerate(row):
            if not _is_plain_int(cell):
                raise SudokuValidationError(
                    f"Cell at row {row_index + 1}, column {col_index + 1} must be "
                    f"an integer, got {type(cell).__name__}."
                )
            if not MIN_VALUE - 1 <= cell <= MAX_VALUE:
                raise SudokuValidationError(
                    f"Cell at row {row_index + 1}, column {col_index + 1} must be "
                    f"between {MIN_VALUE - 1} (empty) and {MAX_VALUE}, got {cell}."
                )


def _find_duplicate_value(values) -> Optional[int]:
    """Return the first duplicated non-zero value, or None if there is none."""
    seen = set()
    for value in values:
        if value == EMPTY_CELL:
            continue
        if value in seen:
            return value
        seen.add(value)
    return None


def validate_initial_clues(grid: Grid) -> None:
    """Raise :class:`SudokuValidationError` if the non-zero clues break Sudoku rules.

    Empty cells (``0``) are ignored. Duplicate clues are reported separately for
    rows, columns, and 3x3 subgrids.
    """
    validate_grid_structure(grid)

    for row in range(GRID_SIZE):
        duplicate = _find_duplicate_value(grid[row])
        if duplicate is not None:
            raise SudokuValidationError(
                f"Duplicate clue value {duplicate} in row {row + 1}."
            )

    for col in range(GRID_SIZE):
        column = [grid[row][col] for row in range(GRID_SIZE)]
        duplicate = _find_duplicate_value(column)
        if duplicate is not None:
            raise SudokuValidationError(
                f"Duplicate clue value {duplicate} in column {col + 1}."
            )

    for top in range(0, GRID_SIZE, BOX_SIZE):
        for left in range(0, GRID_SIZE, BOX_SIZE):
            box = [
                grid[row][col]
                for row in range(top, top + BOX_SIZE)
                for col in range(left, left + BOX_SIZE)
            ]
            duplicate = _find_duplicate_value(box)
            if duplicate is not None:
                raise SudokuValidationError(
                    f"Duplicate clue value {duplicate} in 3x3 subgrid starting "
                    f"at row {top + 1}, column {left + 1}."
                )


def validate_grid(grid: object) -> None:
    """Raise :class:`SudokuValidationError` unless the grid is well-formed and clue-consistent."""
    validate_grid_structure(grid)
    validate_initial_clues(grid)


def is_valid_grid(grid: object) -> bool:
    """Return True if the grid is well-formed and its clues are consistent."""
    try:
        validate_grid(grid)
        return True
    except SudokuValidationError:
        return False


def is_complete(grid: Grid) -> bool:
    """Return True if every cell of a well-formed grid is filled (non-zero).

    Raises :class:`SudokuValidationError` for a malformed grid so that malformed
    input is never mistaken for a merely incomplete puzzle.
    """
    validate_grid_structure(grid)
    return all(cell != EMPTY_CELL for row in grid for cell in row)


def validate_solution(original_grid: Grid, solution_grid: Grid) -> None:
    """Raise :class:`SudokuValidationError` unless ``solution_grid`` solves ``original_grid``.

    The proposed solution must be well-formed, completely filled, obey every
    Sudoku rule, and preserve each non-zero clue of ``original_grid``.
    """
    validate_grid_structure(original_grid)
    validate_grid_structure(solution_grid)

    if not is_complete(solution_grid):
        raise SudokuValidationError(
            "Solution grid is incomplete; some cells are still empty."
        )

    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            if not is_valid_move(solution_grid, row, col, solution_grid[row][col]):
                raise SudokuValidationError(
                    f"Solution violates a Sudoku rule at row {row + 1}, "
                    f"column {col + 1}."
                )

    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            clue = original_grid[row][col]
            if clue != EMPTY_CELL and solution_grid[row][col] != clue:
                raise SudokuValidationError(
                    f"Solution changes the original clue at row {row + 1}, "
                    f"column {col + 1}: expected {clue}, got {solution_grid[row][col]}."
                )


def is_valid_solution(original_grid: Grid, solution_grid: Grid) -> bool:
    """Return True if ``solution_grid`` is a complete, valid solution of ``original_grid``."""
    try:
        validate_solution(original_grid, solution_grid)
        return True
    except SudokuValidationError:
        return False
