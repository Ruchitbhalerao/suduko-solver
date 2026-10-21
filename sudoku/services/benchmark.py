"""Benchmarking service for the three Sudoku solvers (Phase 6).

This module measures how the Phase 3/4/5 solvers behave on a shared, documented
puzzle dataset. It deliberately lives outside ``sudoku.ai``: it *uses* the
solvers, never re-implements them, and it adds only coordination, classification,
aggregation and error handling around their real :class:`SolverResult` output.

Nothing here imports Django.

Public API
----------
* :func:`benchmark_puzzle` -- run one puzzle across one or more algorithms.
* :func:`run_benchmarks` -- run many puzzles, returning a :class:`BenchmarkSuite`.

Measurement rules
-----------------
* The **primary** timing value is each solver's own
  :attr:`SolverResult.execution_time_ms`, which covers only the search. Validation,
  Django, reporting and benchmark overhead are excluded, so the baseline solver is
  never compared against a figure inflated by benchmark plumbing.
* Repeated successful runs report ``repetitions`` plus the median / minimum /
  maximum of those measured times.
* ``recursive_calls``, ``attempted_assignments`` and ``backtracks`` are
  deterministic for a fixed puzzle and implementation, so all repetitions must
  agree. Disagreement is surfaced via ``counters_consistent = False`` (and the
  counter fields are cleared) rather than by silently picking one run.
* Times are reported exactly as measured. A value of ``0.0`` is only ever the
  real measurement; nothing illustrative is ever substituted.
* Solutions are independently re-verified with
  :func:`~sudoku.utils.validation.is_valid_solution`.

Outcome classification
----------------------
``invalid_input`` (malformed or conflicting clues), ``unsolvable`` (valid but no
solution), ``solved`` (verified solution) and ``error`` (unexpected solver
exception). ``invalid_input`` is distinct from ``unsolvable``, and ``error`` is
distinct from both, so an implementation fault can never masquerade as a normal
unsolvable result.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, Union

from sudoku.ai.constraints import Grid
from sudoku.ai.metrics import SolverResult
from sudoku.ai.solvers import ALGORITHM_RUNNERS, ALGORITHMS
from sudoku.utils.puzzles import BENCHMARK_PUZZLES, BenchmarkPuzzle
from sudoku.utils.validation import SudokuValidationError, is_valid_solution

__all__ = [
    "ALGORITHMS",
    "ALGORITHM_RUNNERS",
    "STATUS_SOLVED",
    "STATUS_UNSOLVABLE",
    "STATUS_INVALID_INPUT",
    "STATUS_ERROR",
    "AlgorithmOutcome",
    "PuzzleBenchmark",
    "BenchmarkSuite",
    "benchmark_puzzle",
    "run_benchmarks",
]

# Canonical algorithm identifiers and their solver entry points now live in the
# Django-free registry ``sudoku.ai.solvers``. They are re-exported here so the
# benchmark's public surface (``ALGORITHMS`` / ``ALGORITHM_RUNNERS``) is
# unchanged and callers (and tests) keep working exactly as before.

STATUS_SOLVED = "solved"
STATUS_UNSOLVABLE = "unsolvable"
STATUS_INVALID_INPUT = "invalid_input"
STATUS_ERROR = "error"

PuzzleInput = Union[BenchmarkPuzzle, Grid]


@dataclass(frozen=True)
class AlgorithmOutcome:
    """Aggregated result of running one algorithm on one puzzle.

    Timing and search-counter fields are ``None`` for ``invalid_input`` and
    ``error`` outcomes, because those runs never produced a legitimate
    measurement to aggregate.

    Attributes:
        algorithm: Algorithm identifier.
        status: One of the ``STATUS_*`` constants.
        repetitions: Number of solver runs actually performed.
        median_time_ms / min_time_ms / max_time_ms: Aggregated solver times.
        recursive_calls / attempted_assignments / backtracks: Deterministic
            search counters, or ``None`` if repetitions disagreed.
        counters_consistent: Whether every repetition agreed on all counters.
        solution_valid: ``True``/``False`` for solved runs (independent
            re-verification), ``None`` otherwise.
        error_type / error_message: Populated only for ``invalid_input`` and
            ``error`` so failures stay debuggable.
        note: Human-readable explanation of the outcome.
    """

    algorithm: str
    status: str
    repetitions: int
    median_time_ms: Optional[float]
    min_time_ms: Optional[float]
    max_time_ms: Optional[float]
    recursive_calls: Optional[int]
    attempted_assignments: Optional[int]
    backtracks: Optional[int]
    counters_consistent: bool
    solution_valid: Optional[bool]
    error_type: Optional[str]
    error_message: Optional[str]
    note: str


@dataclass(frozen=True)
class PuzzleBenchmark:
    """All algorithm outcomes for a single puzzle."""

    identifier: str
    category: str
    purpose: str
    outcomes: Tuple[AlgorithmOutcome, ...]


@dataclass(frozen=True)
class BenchmarkSuite:
    """A whole benchmark run: every puzzle, every algorithm."""

    algorithms: Tuple[str, ...]
    repetitions: int
    results: Tuple[PuzzleBenchmark, ...]


def _normalize_algorithms(algorithms: Optional[Sequence[str]]) -> Tuple[str, ...]:
    """Return the requested algorithms in canonical order, validating names."""
    if algorithms is None:
        return ALGORITHMS

    requested = tuple(algorithms)
    if not requested:
        raise ValueError("algorithms must not be empty.")

    unknown = [name for name in requested if name not in ALGORITHM_RUNNERS]
    if unknown:
        raise ValueError(
            f"Unsupported algorithm name(s): {unknown}. "
            f"Supported algorithms are: {list(ALGORITHMS)}."
        )

    ordered = tuple(name for name in ALGORITHMS if name in requested)
    return ordered


def _normalize_repetitions(repetitions: int) -> int:
    """Validate and return the repetition count."""
    if isinstance(repetitions, bool) or not isinstance(repetitions, int):
        raise ValueError(
            f"repetitions must be a positive integer, got {repetitions!r}."
        )
    if repetitions < 1:
        raise ValueError(f"repetitions must be at least 1, got {repetitions}.")
    return repetitions


def _split_puzzle(
    puzzle: PuzzleInput,
    identifier: Optional[str],
    category: Optional[str],
    purpose: Optional[str],
) -> Tuple[str, str, str, Grid]:
    """Unpack either a :class:`BenchmarkPuzzle` or a raw grid."""
    if isinstance(puzzle, BenchmarkPuzzle):
        return (
            identifier or puzzle.identifier,
            category or puzzle.category,
            purpose or puzzle.purpose,
            puzzle.grid,
        )

    grid = puzzle
    if not isinstance(grid, list):
        raise TypeError(
            "puzzle must be a BenchmarkPuzzle or a 9x9 grid (list of rows), "
            f"got {type(grid).__name__}."
        )
    return identifier or "puzzle", category or "unspecified", purpose or "", grid


def _failure_outcome(
    algorithm: str,
    *,
    status: str,
    error_type: str,
    error_message: str,
    note: str,
    repetitions: int = 1,
) -> AlgorithmOutcome:
    """Build an outcome for an input-driven or unexpected failure.

    No timing or search counters are reported: there is no legitimate
    measurement to aggregate, and an unexpected error must never look like a
    successful or ordinary unsolvable run.
    """
    return AlgorithmOutcome(
        algorithm=algorithm,
        status=status,
        repetitions=repetitions,
        median_time_ms=None,
        min_time_ms=None,
        max_time_ms=None,
        recursive_calls=None,
        attempted_assignments=None,
        backtracks=None,
        counters_consistent=True,
        solution_valid=None,
        error_type=error_type,
        error_message=error_message,
        note=note,
    )


def _run_algorithm(
    algorithm: str,
    grid: Grid,
    repetitions: int,
) -> AlgorithmOutcome:
    """Run one algorithm on ``grid`` ``repetitions`` times and aggregate."""
    runner = ALGORITHM_RUNNERS[algorithm]

    times = []
    counter_runs = []
    solution = None
    solved = False

    # invalid_input / error are input- or implementation-determined, so one
    # attempt is enough to classify them; repeats would only repeat the failure.
    for _ in range(repetitions):
        work = [list(row) for row in grid]
        try:
            result = runner(work)
        except SudokuValidationError as exc:
            return _failure_outcome(
                algorithm,
                status=STATUS_INVALID_INPUT,
                error_type=type(exc).__name__,
                error_message=str(exc),
                note=(
                    "Rejected during validation (malformed grid or conflicting "
                    "initial clues); classified as invalid input, not unsolvable. "
                    "Repeats not performed."
                ),
            )
        except Exception as exc:  # noqa: BLE001 - must not become "unsolvable"
            return _failure_outcome(
                algorithm,
                status=STATUS_ERROR,
                error_type=type(exc).__name__,
                error_message=f"{type(exc).__name__}: {exc}",
                note=(
                    "Unexpected solver exception; recorded as an error so it can "
                    "never be mistaken for a successful or ordinary unsolvable "
                    "result. Repeats not performed."
                ),
            )

        if not isinstance(result, SolverResult):
            return _failure_outcome(
                algorithm,
                status=STATUS_ERROR,
                error_type=type(result).__name__,
                error_message=(
                    f"{algorithm} returned {type(result).__name__}, expected "
                    "SolverResult."
                ),
                note=(
                    "Solver returned an unexpected type; recorded as an error. "
                    "Repeats not performed."
                ),
            )

        times.append(float(result.execution_time_ms))
        counter_runs.append(
            (result.recursive_calls, result.attempted_assignments, result.backtracks)
        )
        solved = bool(result.solved)
        solution = result.solution

    outcome_kwargs: dict = {}

    if solved:
        # Independent verification of every reported successful solution.
        if solution is None or not is_valid_solution(grid, solution):
            return _failure_outcome(
                algorithm,
                status=STATUS_ERROR,
                error_type="SolutionVerificationError",
                error_message="Reported solution failed independent verification.",
                note=(
                    "The solver reported solved=True but the solution did not pass "
                    "is_valid_solution; recorded as an error."
                ),
                repetitions=repetitions,
            )
        status = STATUS_SOLVED
        solution_valid: Optional[bool] = True
        note = "Solution independently verified with is_valid_solution."
    else:
        status = STATUS_UNSOLVABLE
        solution_valid = None
        note = (
            f"All {repetitions} run(s) returned solved=False for a "
            "clue-consistent grid."
        )

    # Counter consistency across repetitions.
    counters_consistent = len(set(counter_runs)) == 1
    if counters_consistent:
        calls, assignments, backtracks = counter_runs[0]
        note += " Search counters were identical across repetitions."
    else:
        calls = assignments = backtracks = None
        note += (
            " WARNING: search counters differed across repetitions: "
            f"{sorted(set(counter_runs))}."
        )

    return AlgorithmOutcome(
        algorithm=algorithm,
        status=status,
        repetitions=repetitions,
        median_time_ms=float(statistics.median(times)),
        min_time_ms=min(times),
        max_time_ms=max(times),
        recursive_calls=calls,
        attempted_assignments=assignments,
        backtracks=backtracks,
        counters_consistent=counters_consistent,
        solution_valid=solution_valid,
        error_type=None,
        error_message=None,
        note=note,
    )


def benchmark_puzzle(
    puzzle: PuzzleInput,
    algorithms: Optional[Sequence[str]] = None,
    repetitions: int = 3,
    *,
    identifier: Optional[str] = None,
    category: Optional[str] = None,
    purpose: Optional[str] = None,
) -> PuzzleBenchmark:
    """Benchmark one puzzle across one or more algorithms.

    Args:
        puzzle: A :class:`~sudoku.utils.puzzles.BenchmarkPuzzle` or a raw 9x9
            grid. The source puzzle is never modified; every algorithm and every
            repetition receives its own independent copy.
        algorithms: Names from :data:`ALGORITHMS` (all three by default).
        repetitions: Positive number of runs per algorithm (default 3).
        identifier / category / purpose: Optional metadata overrides, useful
            when passing a raw grid.

    Returns:
        A :class:`PuzzleBenchmark` whose outcomes are ordered by the canonical
        :data:`ALGORITHMS` order.

    Raises:
        ValueError: On an unsupported algorithm name or a non-positive /
            non-integer repetition count.
    """
    ordered_algorithms = _normalize_algorithms(algorithms)
    reps = _normalize_repetitions(repetitions)
    ident, cat, purp, grid = _split_puzzle(puzzle, identifier, category, purpose)

    outcomes = tuple(
        _run_algorithm(name, grid, reps) for name in ordered_algorithms
    )
    return PuzzleBenchmark(
        identifier=ident, category=cat, purpose=purp, outcomes=outcomes
    )


def run_benchmarks(
    puzzles: Optional[Sequence[PuzzleInput]] = None,
    algorithms: Optional[Sequence[str]] = None,
    repetitions: int = 3,
) -> BenchmarkSuite:
    """Benchmark every puzzle (defaults to the whole Phase 6 dataset).

    Results are ordered by puzzle ``identifier`` (ascending); outcomes within a
    puzzle follow the canonical :data:`ALGORITHMS` order. Ordering is therefore
    fully deterministic.

    Raises:
        ValueError: On an unsupported algorithm name or a bad repetition count.
    """
    ordered_algorithms = _normalize_algorithms(algorithms)
    reps = _normalize_repetitions(repetitions)
    source = BENCHMARK_PUZZLES if puzzles is None else tuple(puzzles)

    results = [
        benchmark_puzzle(puzzle, algorithms=ordered_algorithms, repetitions=reps)
        for puzzle in source
    ]
    results.sort(key=lambda item: item.identifier)

    return BenchmarkSuite(
        algorithms=ordered_algorithms, repetitions=reps, results=tuple(results)
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Command-line entry point (``python -m sudoku.services.benchmark``)."""
    import argparse
    from pathlib import Path

    default_output = Path(__file__).resolve().parents[2] / "benchmark_results"

    parser = argparse.ArgumentParser(
        prog="python -m sudoku.services.benchmark",
        description="Benchmark the Sudoku solvers and write CSV/Markdown/SVG reports.",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=3,
        help="Solver runs per puzzle per algorithm (default: 3).",
    )
    parser.add_argument(
        "--algorithms",
        nargs="+",
        default=None,
        metavar="NAME",
        help=f"Subset of algorithms (default: {' '.join(ALGORITHMS)}).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output,
        help=f"Directory for generated reports (default: {default_output}).",
    )
    args = parser.parse_args(argv)

    suite = run_benchmarks(
        algorithms=args.algorithms, repetitions=args.repetitions
    )

    from sudoku.services import reporting  # imported lazily to avoid a cycle

    paths = reporting.write_reports(suite, args.output_dir)

    print(f"Benchmarked {len(suite.results)} puzzle(s), "
          f"algorithms: {', '.join(suite.algorithms)}, "
          f"repetitions: {suite.repetitions}.")
    for label, path in paths.items():
        print(f"  {label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
