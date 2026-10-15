"""Registry of the available Sudoku solving algorithms (single source of truth).

This module maps the public algorithm identifiers to their solver entry points.
It is the one place that knows *which* algorithms exist, so the HTTP API and the
benchmark service agree without duplicating the mapping. Like the rest of the
``sudoku.ai`` package it imports only the AI engine -- never Django -- so it can
be reused and tested on its own.

Public algorithm identifiers
----------------------------
* ``backtracking``         -- basic recursive backtracking (Phase 3 baseline).
* ``mrv``                  -- Minimum Remaining Values heuristic (Phase 4).
* ``mrv_forward_checking`` -- MRV + forward checking (Phase 5).

``DEFAULT_ALGORITHM`` is the algorithm used when a caller does not name one.
"""

from __future__ import annotations

from typing import Callable, Dict, Tuple

from sudoku.ai.backtracking import solve_backtracking
from sudoku.ai.constraints import Grid
from sudoku.ai.forward_checking import solve_forward_checking
from sudoku.ai.metrics import SolverResult
from sudoku.ai.mrv import solve_mrv

__all__ = [
    "ALGORITHMS",
    "ALGORITHM_RUNNERS",
    "DEFAULT_ALGORITHM",
]

# Canonical algorithm identifiers, in the fixed order used for reporting and
# for error messages.
ALGORITHMS: Tuple[str, ...] = ("backtracking", "mrv", "mrv_forward_checking")

# Algorithm used when the caller does not specify one.
DEFAULT_ALGORITHM: str = "backtracking"

# Name -> solver entry point. Kept as a mutable module-level dict so callers
# (and tests) may substitute a runner without touching the solvers themselves.
ALGORITHM_RUNNERS: Dict[str, Callable[[Grid], SolverResult]] = {
    "backtracking": solve_backtracking,
    "mrv": solve_mrv,
    "mrv_forward_checking": solve_forward_checking,
}
