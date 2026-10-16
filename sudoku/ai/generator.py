"""Random Sudoku puzzle generation with uniqueness checking.

This module is part of the Django-free AI engine. It builds a *random* puzzle
and guarantees, by construction, that the puzzle has exactly **one** solution:

1. Fill an empty grid with a complete, valid solution using randomized
   backtracking (every digit ``1``..``9`` is tried in a shuffled order).
2. Remove clues from that solution one at a time in a random order. After each
   tentative removal the solver is asked how many solutions remain; the removal
   is kept only when the answer is still exactly one, otherwise the clue is
   restored.

Because removals are only ever accepted when uniqueness survives, the returned
puzzle is always valid and has a unique solution. Difficulty is expressed as a
target *clue count*: easier puzzles keep more clues. The labels are approximate
by nature -- the exact number of clues is reported alongside the puzzle.

Nothing here imports Django, and callers' grids are never modified.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Tuple

from sudoku.ai.constraints import EMPTY_CELL, GRID_SIZE, Grid, is_valid_move
from sudoku.utils.validation import is_valid_solution, validate_grid

__all__ = [
    "DIFFICULTIES",
    "DIFFICULTY_CLUE_TARGETS",
    "DEFAULT_DIFFICULTY",
    "MIN_CLUES",
    "GeneratedPuzzle",
    "GenerationError",
    "count_solutions",
    "generate_puzzle",
    "generate_solution",
    "has_unique_solution",
]

# Approximate clue-count targets per difficulty. ``easy`` keeps the most clues,
# ``hard`` removes the most. The generator never goes below ``MIN_CLUES`` and
# stops removing when uniqueness would be lost, so the real count can be higher.
DIFFICULTY_CLUE_TARGETS = {
    "easy": 40,
    "medium": 32,
    "hard": 26,
}

DIFFICULTIES = tuple(DIFFICULTY_CLUE_TARGETS)

DEFAULT_DIFFICULTY = "medium"

# A Sudoku puzzle needs at least 17 clues to have a unique solution, so the
# generator refuses to remove clues past this hard floor.
MIN_CLUES = 17

_CELLS = GRID_SIZE * GRID_SIZE
_VALUES = tuple(range(1, GRID_SIZE + 1))


class GenerationError(RuntimeError):
    """Raised when a puzzle cannot be generated or fails verification."""


@dataclass(frozen=True)
class GeneratedPuzzle:
    """A freshly generated puzzle together with its unique solution.

    Attributes:
        puzzle: The 9x9 puzzle grid (``0`` marks an empty cell). Guaranteed to
            be valid and to have exactly one solution.
        solution: The completed 9x9 solution the puzzle was carved from.
        difficulty: The requested difficulty label.
        clues: The number of non-empty clues in ``puzzle``.
        unique: Always True; asserted during generation and recorded explicitly
            so callers do not have to re-check.
    """

    puzzle: Grid
    solution: Grid
    difficulty: str
    clues: int
    unique: bool


def _empty_grid() -> Grid:
    """Return a fresh all-empty 9x9 grid."""
    return [[EMPTY_CELL] * GRID_SIZE for _ in range(GRID_SIZE)]


def _fill(grid: Grid, rng: random.Random) -> bool:
    """Fill ``grid`` in place with a complete solution; return success.

    Uses row-major cell selection but tries the digits in a per-call shuffled
    order, so a different ``rng`` seed yields a different solution.
    """
    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            if grid[row][col] != EMPTY_CELL:
                continue
            candidates: List[int] = list(_VALUES)
            rng.shuffle(candidates)
            for value in candidates:
                if is_valid_move(grid, row, col, value):
                    grid[row][col] = value
                    if _fill(grid, rng):
                        return True
                    grid[row][col] = EMPTY_CELL
            return False
    return True


def generate_solution(rng: Optional[random.Random] = None) -> Grid:
    """Return a complete, valid, randomly generated 9x9 solution.

    Args:
        rng: Optional :class:`random.Random` instance. Passing a seeded one
            makes the result reproducible (used by the tests).

    Raises:
        GenerationError: If the randomized search fails to fill the grid, which
            should never happen on an empty grid.
    """
    generator = rng if rng is not None else random.Random()
    grid = _empty_grid()
    if not _fill(grid, generator):
        raise GenerationError("Failed to fill a complete Sudoku solution.")
    return grid


def _select_mrv_cell(grid: Grid) -> Tuple[Optional[Tuple[int, int]], List[int]]:
    """Return the empty cell with the fewest candidates, plus those candidates.

    Selecting the most-constrained cell keeps uniqueness counting fast. Ties are
    broken in row-major order so counting is deterministic.
    """
    best_cell: Optional[Tuple[int, int]] = None
    best_candidates: List[int] = []

    for row in range(GRID_SIZE):
        for col in range(GRID_SIZE):
            if grid[row][col] != EMPTY_CELL:
                continue
            candidates = [
                value for value in _VALUES if is_valid_move(grid, row, col, value)
            ]
            if best_cell is None or len(candidates) < len(best_candidates):
                best_cell = (row, col)
                best_candidates = candidates
                # A cell with 0 or 1 candidates cannot be beaten; stop early.
                if len(candidates) <= 1:
                    return best_cell, best_candidates
    return best_cell, best_candidates


def _count(grid: Grid, limit: int) -> int:
    """Count solutions of ``grid`` in place, stopping once ``limit`` is reached."""
    cell, candidates = _select_mrv_cell(grid)
    if cell is None:
        return 1
    if not candidates:
        return 0

    row, col = cell
    total = 0
    for value in candidates:
        grid[row][col] = value
        total += _count(grid, limit - total)
        grid[row][col] = EMPTY_CELL
        if total >= limit:
            break
    return total


def count_solutions(puzzle: Grid, limit: int = 2) -> int:
    """Return the number of solutions of ``puzzle``, capped at ``limit``.

    The caller's grid is never modified. A ``limit`` of ``2`` is enough to tell
    "unique" (``1``) from "not unique" (``2`` or more) while staying cheap.

    Raises:
        ValueError: If ``limit`` is less than 1.
        SudokuValidationError: If ``puzzle`` is malformed or its clues conflict.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer.")

    validate_grid(puzzle)
    working = [list(row) for row in puzzle]
    return _count(working, limit)


def has_unique_solution(puzzle: Grid) -> bool:
    """Return True when ``puzzle`` has exactly one solution."""
    return count_solutions(puzzle, limit=2) == 1


def generate_puzzle(
    difficulty: str = DEFAULT_DIFFICULTY,
    *,
    rng: Optional[random.Random] = None,
    min_clues: Optional[int] = None,
) -> GeneratedPuzzle:
    """Generate a valid puzzle with a unique solution.

    Args:
        difficulty: One of :data:`DIFFICULTIES`. Selects the clue-count target.
        rng: Optional seeded :class:`random.Random` for reproducible output.
        min_clues: Optional explicit clue-count floor, overriding the difficulty
            target.

    Returns:
        A :class:`GeneratedPuzzle` whose ``puzzle`` is valid and unique.

    Raises:
        ValueError: For an unknown difficulty or an out-of-range ``min_clues``.
        GenerationError: If the finished puzzle fails independent verification.
    """
    if difficulty not in DIFFICULTY_CLUE_TARGETS:
        supported = ", ".join(DIFFICULTIES)
        raise ValueError(
            f"Unknown difficulty {difficulty!r}. Supported difficulties: {supported}."
        )

    if min_clues is None:
        clue_floor = DIFFICULTY_CLUE_TARGETS[difficulty]
    elif not isinstance(min_clues, int) or isinstance(min_clues, bool):
        raise ValueError("min_clues must be an integer.")
    else:
        if not MIN_CLUES <= min_clues <= _CELLS:
            raise ValueError(
                f"min_clues must be between {MIN_CLUES} and {_CELLS}, got {min_clues}."
            )
        clue_floor = min_clues

    generator = rng if rng is not None else random.Random()
    solution = generate_solution(generator)

    puzzle = [list(row) for row in solution]
    positions = [(row, col) for row in range(GRID_SIZE) for col in range(GRID_SIZE)]
    generator.shuffle(positions)

    remaining = _CELLS
    for row, col in positions:
        if remaining <= clue_floor:
            break
        saved = puzzle[row][col]
        puzzle[row][col] = EMPTY_CELL
        if count_solutions(puzzle, limit=2) == 1:
            remaining -= 1
        else:
            puzzle[row][col] = saved

    if not is_valid_solution(puzzle, solution):
        raise GenerationError(
            "Generated puzzle failed solution verification."
        )
    if count_solutions(puzzle, limit=2) != 1:
        raise GenerationError(
            "Generated puzzle does not have exactly one solution."
        )

    return GeneratedPuzzle(
        puzzle=puzzle,
        solution=solution,
        difficulty=difficulty,
        clues=remaining,
        unique=True,
    )
