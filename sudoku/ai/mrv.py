"""Minimum Remaining Values (MRV) Sudoku solver (Phase 4).

This is the first heuristic solver. It uses the same constraint primitives as
the baseline backtracking solver but changes *which cell* is filled next: at
every step it selects the empty cell with the fewest legal candidates
(``get_candidates``), which tends to fail fast on doomed branches.

MRV selection
-------------
1. Inspect every currently empty cell.
2. Compute its legal candidates with :func:`get_candidates`.
3. Choose the empty cell with the **fewest** legal candidates.
4. Break ties deterministically by row, then column (row-major order).
5. If the chosen cell has zero candidates, the branch fails immediately.
6. If no empty cell remains, the puzzle is solved.

Candidates are still tried in ascending order. Unlike the baseline solver, the
cell is not chosen by row-major order; only *ties* are resolved that way.

Counter definitions (identical to the baseline solver)
------------------------------------------------------
* ``recursive_calls``: incremented every time the recursive search function is
  entered, including the initial invocation.
* ``attempted_assignments``: incremented every time a candidate value is placed
  into a cell for testing.
* ``backtracks``: incremented every time an attempted assignment fails and is
  undone.
* ``execution_time_ms``: wall-clock time of the search, measured with
  ``time.perf_counter()`` and bounded the same way as the baseline solver.

This module never imports Django, so the AI engine stays framework-independent.
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

from sudoku.ai.backtracking import SolverError
from sudoku.ai.constraints import EMPTY_CELL, GRID_SIZE, Grid, get_candidates
from sudoku.ai.metrics import SearchMetrics, SolverResult
from sudoku.utils.validation import is_valid_solution, validate_grid


def select_mrv_cell(grid: Grid) -> Optional[Tuple[int, int]]:
    """Return the empty cell with the fewest legal candidates.

    Ties for the fewest candidates are broken deterministically by row and then
    column, so the first such cell in row-major order wins. A cell with zero
    candidates is a valid (and minimal) result; the caller treats it as an
    immediate dead end.

    Returns:
        ``(row, col)`` of the selected empty cell, or None if the grid is
        already complete.
    """
    best_cell: Optional[Tuple[int, int]] = None
    best_count: Optional[int] = None

    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            if grid[row][col] != EMPTY_CELL:
                continue
            count = len(get_candidates(grid, row, col))
            if best_count is None or count < best_count:
                best_count = count
                best_cell = (row, col)

    return best_cell


def solve_mrv(grid: Grid) -> SolverResult:
    """Solve ``grid`` with recursive backtracking using the MRV heuristic.

    Args:
        grid: A 9x9 Sudoku grid using ``0`` for empty cells and ``1``..``9`` for
            clues. The grid is not modified.

    Returns:
        A :class:`SolverResult`. When a solution exists, ``solved`` is True and
        ``solution`` holds the completed grid; otherwise ``solved`` is False and
        ``solution`` is None. The performance counters and execution time are
        always populated.

    Raises:
        SudokuValidationError: If ``grid`` is malformed or its clues conflict
            (duplicate non-zero values in a row, column, or 3x3 subgrid).
            Malformed input is never reported as merely unsolvable.
        SolverError: If the found solution fails independent verification.
    """
    validate_grid(grid)

    working = [list(row) for row in grid]
    metrics = SearchMetrics()

    start = time.perf_counter()
    solved = _search(working, metrics)
    execution_time_ms = (time.perf_counter() - start) * 1000.0

    if solved:
        if not is_valid_solution(grid, working):
            raise SolverError(
                "MRV search produced a grid that failed solution verification."
            )
        return SolverResult.from_metrics(
            solved=True,
            solution=working,
            execution_time_ms=execution_time_ms,
            metrics=metrics,
        )

    return SolverResult.from_metrics(
        solved=False,
        solution=None,
        execution_time_ms=execution_time_ms,
        metrics=metrics,
    )


def _search(grid: Grid, metrics: SearchMetrics) -> bool:
    """Recursively fill ``grid`` in place; return True once it is solved.

    ``grid`` is the solver's working copy, so mutating it does not affect the
    caller's puzzle.
    """
    metrics.recursive_calls += 1

    cell = select_mrv_cell(grid)
    if cell is None:
        return True

    row, col = cell
    candidates = get_candidates(grid, row, col)
    for candidate in candidates:
        grid[row][col] = candidate
        metrics.attempted_assignments += 1

        if _search(grid, metrics):
            return True

        grid[row][col] = EMPTY_CELL
        metrics.backtracks += 1

    return False
