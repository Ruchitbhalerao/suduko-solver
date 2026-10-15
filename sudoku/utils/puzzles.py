"""Representative Sudoku dataset for benchmarking (Phase 6).

A small, documented collection of puzzles used as the input set for
``sudoku.services.benchmark``. Everything here is framework-free: only the grid
type from :mod:`sudoku.ai.constraints` is imported, so the dataset can be used
without Django.

Difficulty labels
-----------------
Difficulty labels (``easy`` / ``medium`` / ``hard``) are **approximate**. They
are *not* taken from a rating service and are not authoritative human puzzle
ratings. They were assigned by comparing the measured *search effort* of the
Phase 3 baseline backtracking solver on each puzzle, which is fully
deterministic for a fixed puzzle and implementation:

* ``easy_classic``  -> 4,209 recursive calls
* ``medium_classic`` -> 15,495 recursive calls
* ``hard_inkala``   -> 49,559 recursive calls

Those counts (unlike wall-clock timings) are reproducible, so they give a real,
if rough, ordering of relative difficulty. Every label in ``category`` is
written as ``"<approximate tier> (approx.)"`` to make the uncertainty explicit.

Data sources
------------
* ``easy_classic`` and ``already_completed`` use the same well-known puzzle and
  solution that the test fixtures rely on (``sudoku.tests.fixtures``), copied
  here so that the benchmark dataset stays independent of the test package.
* ``medium_classic`` is a commonly published medium puzzle.
* ``hard_inkala`` is the well-known "world's hardest Sudoku" by Arto Inkala
  (2012), included because it is sparse and forces a large baseline search. It
  is deliberately *not* an empty grid: an empty grid would create an
  unrepresentative baseline run.

Each entry documents its purpose. The dataset includes the four outcome classes
the benchmark service must distinguish: solvable (three difficulty tiers), an
already-completed grid, a valid-but-unsolvable puzzle, and an invalid puzzle
with conflicting clues.
"""

from __future__ import annotations

from dataclasses import dataclass

from sudoku.ai.constraints import Grid

__all__ = ["BenchmarkPuzzle", "BENCHMARK_PUZZLES", "get_puzzle"]


@dataclass(frozen=True)
class BenchmarkPuzzle:
    """One benchmark input.

    Attributes:
        identifier: Stable, machine-friendly slug used for ordering and report
            keys (lower-case snake_case).
        category: Human-readable, **approximate** difficulty/category label.
        purpose: Why this puzzle is part of the dataset and what it exercises.
        grid: The 9x9 puzzle grid (``0`` = empty). Callers must treat it as
            read-only; the benchmark service always works on copies.
    """

    identifier: str
    category: str
    purpose: str
    grid: Grid


# A known-complete, valid Sudoku solution (the classic "Wikipedia" solution).
_VALID_SOLUTION: Grid = [
    [5, 3, 4, 6, 7, 8, 9, 1, 2],
    [6, 7, 2, 1, 9, 5, 3, 4, 8],
    [1, 9, 8, 3, 4, 2, 5, 6, 7],
    [8, 5, 9, 7, 6, 1, 4, 2, 3],
    [4, 2, 6, 8, 5, 3, 7, 9, 1],
    [7, 1, 3, 9, 2, 4, 8, 5, 6],
    [9, 6, 1, 5, 3, 7, 2, 8, 4],
    [2, 8, 7, 4, 1, 9, 6, 3, 5],
    [3, 4, 5, 2, 8, 6, 1, 7, 9],
]

# The classic easy puzzle derived from _VALID_SOLUTION (30 clues).
_EASY_PUZZLE: Grid = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0],
    [6, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 8, 0, 0, 7, 9],
]

_MEDIUM_PUZZLE: Grid = [
    [0, 2, 0, 6, 0, 8, 0, 0, 0],
    [5, 8, 0, 0, 0, 9, 7, 0, 0],
    [0, 0, 0, 0, 4, 0, 0, 0, 0],
    [3, 7, 0, 0, 0, 0, 0, 0, 5],
    [6, 0, 0, 0, 0, 0, 0, 0, 4],
    [8, 0, 0, 0, 0, 0, 0, 9, 3],
    [0, 0, 0, 0, 1, 0, 0, 0, 0],
    [0, 0, 0, 5, 0, 0, 6, 4, 2],
    [0, 0, 0, 4, 0, 6, 0, 8, 0],
]

# Arto Inkala's (2012) sparse, notoriously difficult puzzle.
_HARD_PUZZLE: Grid = [
    [8, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 3, 6, 0, 0, 0, 0, 0],
    [0, 7, 0, 0, 9, 0, 2, 0, 0],
    [0, 5, 0, 0, 0, 7, 0, 0, 0],
    [0, 0, 0, 0, 4, 5, 7, 0, 0],
    [0, 0, 0, 1, 0, 0, 0, 3, 0],
    [0, 0, 1, 0, 0, 0, 0, 6, 8],
    [0, 0, 8, 5, 0, 0, 0, 1, 0],
    [0, 9, 0, 0, 0, 0, 4, 0, 0],
]

# Structurally valid and clue-consistent but unsolvable: cell (0, 0) has no
# legal candidate (its row supplies 1..8 and its column supplies 9).
_UNSOLVABLE_PUZZLE: Grid = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8],
    [9, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
]

# The easy puzzle with a conflicting clue: row 1 would contain two 5s. The grid
# is well-formed but its initial clues break Sudoku rules, so every solver must
# reject it as invalid input rather than reporting it as unsolvable.
_INVALID_PUZZLE: Grid = [
    [5, 3, 0, 0, 7, 0, 0, 0, 5],
    [6, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 8, 0, 0, 7, 9],
]


BENCHMARK_PUZZLES: tuple[BenchmarkPuzzle, ...] = (
    BenchmarkPuzzle(
        identifier="easy_classic",
        category="easy (approx.)",
        purpose=(
            "Clue-rich classic puzzle; the cheapest solvable case. Establishes a "
            "low-effort baseline for all three solvers."
        ),
        grid=_EASY_PUZZLE,
    ),
    BenchmarkPuzzle(
        identifier="medium_classic",
        category="medium (approx.)",
        purpose=(
            "Moderately constrained puzzle where the baseline backtracker already "
            "needs a clearly larger search than the easy case."
        ),
        grid=_MEDIUM_PUZZLE,
    ),
    BenchmarkPuzzle(
        identifier="hard_inkala",
        category="hard (approx.)",
        purpose=(
            "Sparse, high-effort puzzle (highest measured baseline search effort). "
            "Also exposes per-step heuristic overhead: the heuristics take far fewer "
            "search steps yet can spend more wall-clock time selecting cells."
        ),
        grid=_HARD_PUZZLE,
    ),
    BenchmarkPuzzle(
        identifier="already_completed",
        category="already solved",
        purpose=(
            "Valid, complete grid with no empty cells; solvers must accept it "
            "immediately without assigning anything."
        ),
        grid=_VALID_SOLUTION,
    ),
    BenchmarkPuzzle(
        identifier="unsolvable_no_duplicates",
        category="unsolvable",
        purpose=(
            "Well-formed and clue-consistent but provably unsolvable; must be "
            "classified as unsolvable, never as invalid input."
        ),
        grid=_UNSOLVABLE_PUZZLE,
    ),
    BenchmarkPuzzle(
        identifier="invalid_duplicate_clues",
        category="invalid",
        purpose=(
            "Conflicting initial clues (duplicate 5 in row 1); must be classified "
            "as invalid input, never as unsolvable."
        ),
        grid=_INVALID_PUZZLE,
    ),
)


def get_puzzle(identifier: str) -> BenchmarkPuzzle:
    """Return the dataset entry with ``identifier``.

    Raises ``KeyError`` when the identifier is unknown.
    """
    for puzzle in BENCHMARK_PUZZLES:
        if puzzle.identifier == identifier:
            return puzzle
    raise KeyError(f"Unknown benchmark puzzle identifier: {identifier!r}")
