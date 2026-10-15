"""Basic recursive backtracking Sudoku solver (Phase 3 baseline).

This is the reference implementation that the later heuristics (MRV and
forward checking) will be compared against. It deliberately uses no heuristic:
it always picks the first empty cell in row-major order and tries candidate
values in ascending order.

Algorithm
---------
1. Validate the input grid (structure and initial clues).
2. Copy the grid so the caller's puzzle is never modified.
3. Recursively:
   a. Find the next empty cell with :func:`find_empty_cell` (row-major order).
   b. If none remains, the puzzle is solved.
   c. Otherwise, try each candidate from :func:`get_candidates` in ascending
      order: assign it, recurse, and undo the assignment if the recursion fails.
4. Verify every reported solution with :func:`is_valid_solution`.

This module never imports Django, so the AI engine stays framework-independent.

Counter definitions
-------------------
* ``recursive_calls``: incremented every time the recursive search function is
  entered, including the initial invocation.
* ``attempted_assignments``: incremented every time a candidate value is placed
  into a cell for testing.
* ``backtracks``: incremented every time an attempted assignment fails and is
  undone.
* ``execution_time_ms``: wall-clock time of the search, measured with
  ``time.perf_counter()``.
"""

from __future__ import annotations

import time

from sudoku.ai.constraints import EMPTY_CELL, Grid, find_empty_cell, get_candidates
from sudoku.ai.metrics import SearchMetrics, SolverResult
from sudoku.utils.validation import is_valid_solution, validate_grid


class SolverError(RuntimeError):
    """Raised when the solver detects an internal inconsistency.

    This is a safety net: it should never occur in normal operation, because it
    means the algorithm produced a grid that failed independent verification.
    """


def solve_backtracking(grid: Grid) -> SolverResult:
    """Solve ``grid`` with basic recursive backtracking.

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
                "Backtracking produced a grid that failed solution verification."
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

    cell = find_empty_cell(grid)
    if cell is None:
        return True

    row, col = cell
    for candidate in get_candidates(grid, row, col):
        grid[row][col] = candidate
        metrics.attempted_assignments += 1

        if _search(grid, metrics):
            return True

        grid[row][col] = EMPTY_CELL
        metrics.backtracks += 1

    return False
