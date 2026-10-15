"""Result and metric structures shared by the Sudoku solvers.

Keeping these in one small, dependency-light module lets the backtracking
solver (Phase 3) and the later MRV / forward-checking solvers report results
and performance counters consistently. Nothing here imports Django.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sudoku.ai.constraints import Grid


@dataclass
class SearchMetrics:
    """Mutable counters collected while a search runs.

    Attributes:
        recursive_calls: Number of times the recursive search function was
            entered, including the initial invocation.
        attempted_assignments: Number of candidate values written into a cell
            for testing.
        backtracks: Number of attempted assignments that failed and were undone.
    """

    recursive_calls: int = 0
    attempted_assignments: int = 0
    backtracks: int = 0


@dataclass(frozen=True)
class SolverResult:
    """Immutable outcome of a solver run.

    Attributes:
        solved: True if a solution was found, False otherwise.
        solution: The completed 9x9 grid, or None when the puzzle is unsolvable.
        execution_time_ms: Solver execution time in milliseconds, measured with
            ``time.perf_counter()``. It covers only the search itself and
            excludes validation, test setup, Django, and any rendering.
        recursive_calls: See :class:`SearchMetrics`.
        attempted_assignments: See :class:`SearchMetrics`.
        backtracks: See :class:`SearchMetrics`.
    """

    solved: bool
    solution: Optional[Grid]
    execution_time_ms: float
    recursive_calls: int
    attempted_assignments: int
    backtracks: int

    @classmethod
    def from_metrics(
        cls,
        *,
        solved: bool,
        solution: Optional[Grid],
        execution_time_ms: float,
        metrics: SearchMetrics,
    ) -> "SolverResult":
        """Build a result from a finished :class:`SearchMetrics`."""
        return cls(
            solved=solved,
            solution=solution,
            execution_time_ms=execution_time_ms,
            recursive_calls=metrics.recursive_calls,
            attempted_assignments=metrics.attempted_assignments,
            backtracks=metrics.backtracks,
        )
