"""MRV + Forward Checking Sudoku solver (Phase 5).

Combines the Minimum Remaining Values (MRV) heuristic with forward checking.

Forward checking, as implemented here, detects domain wipeout immediately after
a tentative assignment: after assigning a value to the MRV-selected cell, we
check that every remaining empty cell still has at least one legal candidate
given the new grid state. If any empty cell has zero candidates, the branch is
rejected before recursing. No full constraint propagation is performed; only
immediate wipeout is detected.

Counter definitions (identical to the other solvers)
------------------------------------------------------
* ``recursive_calls``: incremented every time the recursive search function is
  entered, including the initial invocation.
* ``attempted_assignments``: incremented every time a candidate value is placed
  into a cell for testing.
* ``backtracks``: incremented every time an attempted assignment fails and is
  undone. This includes candidates rejected by forward checking: their
  assignment is undone and counted as a backtrack, even though no further
  recursion happened.
* ``execution_time_ms``: wall-clock time of the search, measured with
  ``time.perf_counter()`` and bounded the same way as the baseline/MRV solvers.
"""

from __future__ import annotations

import time

from sudoku.ai.backtracking import SolverError
from sudoku.ai.constraints import EMPTY_CELL, GRID_SIZE, Grid, get_candidates
from sudoku.ai.metrics import SearchMetrics, SolverResult
from sudoku.ai.mrv import select_mrv_cell
from sudoku.utils.validation import is_valid_solution, validate_grid


def solve_forward_checking(grid: Grid) -> SolverResult:
    """Solve ``grid`` with MRV + forward checking.

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
                "Forward checking search produced a grid that failed solution verification."
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


def forward_check(grid: Grid) -> bool:
    """Return False if any remaining empty cell has zero legal candidates.

    This detects immediate domain wipeout after a tentative assignment. Only
    empty cells are considered. The caller uses the return value to reject a
    search branch before recursing.
    """
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            if grid[row][col] == EMPTY_CELL:
                candidates = get_candidates(grid, row, col)
                if len(candidates) == 0:
                    return False
    return True


def _search(grid: Grid, metrics: SearchMetrics) -> bool:
    """Recursively fill ``grid`` in place; return True once it is solved."""
    metrics.recursive_calls += 1

    cell = select_mrv_cell(grid)
    if cell is None:
        return True

    row, col = cell
    for candidate in get_candidates(grid, row, col):
        grid[row][col] = candidate
        metrics.attempted_assignments += 1

        if forward_check(grid):
            if _search(grid, metrics):
                return True

        grid[row][col] = EMPTY_CELL
        metrics.backtracks += 1

    return False
