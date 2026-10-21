"""Tests for the Phase 6 benchmark service and report generation.

These tests never assert exact timing values (those are machine-dependent) and
never assume one algorithm must always be fastest. They focus on the service's
contract: classification, fairness, determinism, error handling and output.
"""

from __future__ import annotations

import copy
import csv
import subprocess
import sys
import textwrap
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import SimpleTestCase

from sudoku.ai.backtracking import SolverError, solve_backtracking
from sudoku.ai.forward_checking import solve_forward_checking
from sudoku.ai.metrics import SolverResult
from sudoku.ai.mrv import solve_mrv
from sudoku.services import benchmark as bench
from sudoku.services import reporting
from sudoku.utils.puzzles import BENCHMARK_PUZZLES, BenchmarkPuzzle, get_puzzle
from sudoku.utils.validation import (
    SudokuValidationError,
    is_valid_grid,
    is_valid_solution,
)

# A fast subset used by most tests (avoids the deliberately expensive hard case).
_FAST_IDS = (
    "easy_classic",
    "already_completed",
    "unsolvable_no_duplicates",
    "invalid_duplicate_clues",
)


def _fast_puzzles():
    return [get_puzzle(identifier) for identifier in _FAST_IDS]


def _fake_result(
    *,
    solved: bool = False,
    solution=None,
    execution_time_ms: float = 0.0,
    recursive_calls: int = 0,
    attempted_assignments: int = 0,
    backtracks: int = 0,
) -> SolverResult:
    return SolverResult(
        solved=solved,
        solution=solution,
        execution_time_ms=execution_time_ms,
        recursive_calls=recursive_calls,
        attempted_assignments=attempted_assignments,
        backtracks=backtracks,
    )


class AlgorithmRegistryTests(SimpleTestCase):
    """The three algorithm identifiers and their argument validation."""

    def test_all_three_algorithms_registered(self):
        self.assertEqual(set(bench.ALGORITHMS), set(bench.ALGORITHM_RUNNERS))
        for runner in bench.ALGORITHM_RUNNERS.values():
            self.assertTrue(callable(runner))

    def test_registry_maps_to_the_real_solvers(self):
        self.assertIs(bench.ALGORITHM_RUNNERS["backtracking"], solve_backtracking)
        self.assertIs(bench.ALGORITHM_RUNNERS["mrv"], solve_mrv)
        self.assertIs(
            bench.ALGORITHM_RUNNERS["mrv_forward_checking"], solve_forward_checking
        )

    def test_algorithms_are_accepted_in_canonical_order(self):
        suite = bench.run_benchmarks(
            puzzles=_fast_puzzles()[:1],
            algorithms=["mrv_forward_checking", "backtracking", "mrv"],
            repetitions=1,
        )
        self.assertEqual(suite.algorithms, bench.ALGORITHMS)

    def test_unsupported_algorithm_is_rejected(self):
        with self.assertRaises(ValueError):
            bench.benchmark_puzzle(get_puzzle("easy_classic"), algorithms=["nope"])
        with self.assertRaises(ValueError):
            bench.run_benchmarks(puzzles=_fast_puzzles()[:1], algorithms=["nope"])

    def test_empty_algorithm_list_is_rejected(self):
        with self.assertRaises(ValueError):
            bench.benchmark_puzzle(get_puzzle("easy_classic"), algorithms=[])

    def test_invalid_repetition_counts_are_rejected(self):
        for bad in (0, -1, 1.5, True, "3"):
            with self.subTest(repetitions=bad):
                with self.assertRaises(ValueError):
                    bench.benchmark_puzzle(
                        get_puzzle("easy_classic"), repetitions=bad
                    )


class FairnessTests(SimpleTestCase):
    """Every algorithm gets an equivalent, independent copy of the puzzle."""

    def test_each_algorithm_receives_an_equivalent_independent_copy(self):
        source = get_puzzle("easy_classic").grid
        original = copy.deepcopy(source)
        received = []

        def spy(name):
            def runner(grid):
                received.append((name, [row[:] for row in grid], grid is source))
                grid[0][0] = 9  # mutate the copy; must not affect source or peers
                return _fake_result()

            return runner

        patched = {name: spy(name) for name in bench.ALGORITHMS}
        with mock.patch.dict(bench.ALGORITHM_RUNNERS, patched):
            bench.benchmark_puzzle(
                get_puzzle("easy_classic"), repetitions=2
            )

        self.assertEqual(len(received), len(bench.ALGORITHMS) * 2)
        for name, grid, is_source in received:
            self.assertFalse(is_source, f"{name} received the source object itself")
            self.assertEqual(grid, original, f"{name} received altered content")
        self.assertEqual(source, original, "source puzzle was mutated")

    def test_source_puzzle_is_not_mutated_by_a_real_run(self):
        for puzzle in _fast_puzzles():
            with self.subTest(puzzle=puzzle.identifier):
                original = copy.deepcopy(puzzle.grid)
                bench.benchmark_puzzle(puzzle, repetitions=1)
                self.assertEqual(puzzle.grid, original)

    def test_successful_solution_is_independently_validated(self):
        result = bench.benchmark_puzzle(get_puzzle("easy_classic"), repetitions=1)
        for outcome in result.outcomes:
            self.assertEqual(outcome.status, bench.STATUS_SOLVED)
            self.assertTrue(outcome.solution_valid)
        # Independently re-run one solver and re-check the solution.
        solved = solve_mrv(get_puzzle("easy_classic").grid)
        self.assertTrue(is_valid_solution(get_puzzle("easy_classic").grid, solved.solution))


class ClassificationTests(SimpleTestCase):
    """Solved, completed, unsolvable and invalid inputs are distinguished."""

    def test_completed_puzzle_is_solved_with_no_assignments(self):
        result = bench.benchmark_puzzle(get_puzzle("already_completed"), repetitions=1)
        for outcome in result.outcomes:
            self.assertEqual(outcome.status, bench.STATUS_SOLVED)
            self.assertEqual(outcome.recursive_calls, 1)
            self.assertEqual(outcome.attempted_assignments, 0)
            self.assertEqual(outcome.backtracks, 0)

    def test_invalid_clues_are_reported_as_invalid_input(self):
        result = bench.benchmark_puzzle(
            get_puzzle("invalid_duplicate_clues"), repetitions=1
        )
        for outcome in result.outcomes:
            self.assertEqual(outcome.status, bench.STATUS_INVALID_INPUT)
            self.assertNotEqual(outcome.status, bench.STATUS_UNSOLVABLE)
            self.assertEqual(outcome.error_type, "SudokuValidationError")
            self.assertIsNone(outcome.median_time_ms)
            self.assertIsNone(outcome.recursive_calls)

    def test_unsolvable_puzzle_is_reported_as_unsolvable(self):
        result = bench.benchmark_puzzle(
            get_puzzle("unsolvable_no_duplicates"), repetitions=1
        )
        for outcome in result.outcomes:
            self.assertEqual(outcome.status, bench.STATUS_UNSOLVABLE)
            self.assertIsNone(outcome.solution_valid)
            self.assertIsNotNone(outcome.median_time_ms)


class DeterminismTests(SimpleTestCase):
    """Ordering and repeated-run counter consistency are deterministic."""

    def test_results_are_ordered_by_puzzle_identifier(self):
        shuffled = list(reversed(_fast_puzzles()))
        suite = bench.run_benchmarks(puzzles=shuffled, repetitions=1)
        identifiers = [puzzle.identifier for puzzle in suite.results]
        self.assertEqual(identifiers, sorted(identifiers))

    def test_outcomes_follow_canonical_algorithm_order(self):
        result = bench.benchmark_puzzle(get_puzzle("easy_classic"), repetitions=1)
        self.assertEqual(
            [outcome.algorithm for outcome in result.outcomes], list(bench.ALGORITHMS)
        )

    def test_repeated_runs_have_consistent_counters(self):
        result = bench.benchmark_puzzle(get_puzzle("easy_classic"), repetitions=3)
        for outcome in result.outcomes:
            self.assertEqual(outcome.status, bench.STATUS_SOLVED)
            self.assertTrue(outcome.counters_consistent)

    def test_heuristic_uses_fewer_recursive_calls_than_baseline(self):
        result = bench.benchmark_puzzle(get_puzzle("easy_classic"), repetitions=1)
        by_name = {outcome.algorithm: outcome for outcome in result.outcomes}
        # Deterministic counters: MRV explores far fewer cells than the baseline.
        self.assertLess(
            by_name["mrv"].recursive_calls,
            by_name["backtracking"].recursive_calls,
        )


class ErrorHandlingTests(SimpleTestCase):
    """Unexpected errors never masquerade as normal outcomes."""

    def test_unexpected_exception_is_recorded_as_error(self):
        def boom(grid):
            raise RuntimeError("kaboom")

        with mock.patch.dict(bench.ALGORITHM_RUNNERS, {"mrv": boom}):
            result = bench.benchmark_puzzle(get_puzzle("easy_classic"), repetitions=1)

        by_name = {outcome.algorithm: outcome for outcome in result.outcomes}
        error = by_name["mrv"]
        self.assertEqual(error.status, bench.STATUS_ERROR)
        self.assertNotIn(error.status, (bench.STATUS_SOLVED, bench.STATUS_UNSOLVABLE))
        self.assertEqual(error.error_type, "RuntimeError")
        self.assertIn("kaboom", error.error_message)
        self.assertIsNone(error.median_time_ms)
        # The other algorithms are unaffected.
        self.assertEqual(by_name["backtracking"].status, bench.STATUS_SOLVED)

    def test_solver_error_class_is_recorded_as_error(self):
        def boom(grid):
            raise SolverError("verification failed")

        with mock.patch.dict(bench.ALGORITHM_RUNNERS, {"mrv_forward_checking": boom}):
            result = bench.benchmark_puzzle(get_puzzle("easy_classic"), repetitions=1)

        outcome = next(o for o in result.outcomes if o.algorithm == "mrv_forward_checking")
        self.assertEqual(outcome.status, bench.STATUS_ERROR)
        self.assertEqual(outcome.error_type, "SolverError")

    def test_wrong_return_type_is_recorded_as_error(self):
        with mock.patch.dict(bench.ALGORITHM_RUNNERS, {"mrv": lambda grid: "nope"}):
            result = bench.benchmark_puzzle(get_puzzle("easy_classic"), repetitions=1)

        outcome = next(o for o in result.outcomes if o.algorithm == "mrv")
        self.assertEqual(outcome.status, bench.STATUS_ERROR)
        self.assertIsNone(outcome.median_time_ms)

    def test_validation_error_is_classified_as_invalid_input(self):
        def reject(grid):
            raise SudokuValidationError("bad clues")

        with mock.patch.dict(bench.ALGORITHM_RUNNERS, {"mrv": reject}):
            result = bench.benchmark_puzzle(get_puzzle("easy_classic"), repetitions=1)

        outcome = next(o for o in result.outcomes if o.algorithm == "mrv")
        self.assertEqual(outcome.status, bench.STATUS_INVALID_INPUT)
        self.assertEqual(outcome.error_type, "SudokuValidationError")


class DatasetTests(SimpleTestCase):
    """The benchmark dataset is documented and validated."""

    def test_identifiers_are_unique(self):
        identifiers = [puzzle.identifier for puzzle in BENCHMARK_PUZZLES]
        self.assertEqual(len(identifiers), len(set(identifiers)))

    def test_required_categories_are_present(self):
        identifiers = {puzzle.identifier for puzzle in BENCHMARK_PUZZLES}
        self.assertLessEqual(
            {
                "easy_classic",
                "medium_classic",
                "hard_inkala",
                "already_completed",
                "unsolvable_no_duplicates",
                "invalid_duplicate_clues",
            },
            identifiers,
        )

    def test_every_puzzle_is_well_formed_and_clue_consistent_except_the_invalid_one(self):
        for puzzle in BENCHMARK_PUZZLES:
            with self.subTest(puzzle=puzzle.identifier):
                if puzzle.identifier == "invalid_duplicate_clues":
                    self.assertFalse(is_valid_grid(puzzle.grid))
                else:
                    self.assertTrue(is_valid_grid(puzzle.grid))

    def test_get_puzzle_rejects_unknown_identifier(self):
        with self.assertRaises(KeyError):
            get_puzzle("does_not_exist")


class OutputGenerationTests(SimpleTestCase):
    """CSV/Markdown/SVG writers produce the expected files and contents."""

    @staticmethod
    def _small_suite(repetitions: int = 1):
        return bench.run_benchmarks(puzzles=_fast_puzzles(), repetitions=repetitions)

    def test_write_reports_creates_all_four_files(self):
        with TemporaryDirectory() as directory:
            paths = reporting.write_reports(self._small_suite(), Path(directory))
            self.assertEqual(
                {path.name for path in paths.values()},
                {
                    reporting.RESULTS_CSV,
                    reporting.REPORT_MD,
                    reporting.EXECUTION_TIME_SVG,
                    reporting.SEARCH_EFFORT_SVG,
                },
            )
            for path in paths.values():
                self.assertTrue(path.exists())
                self.assertGreater(path.stat().st_size, 0)

    def test_csv_has_header_and_actual_measurements(self):
        with TemporaryDirectory() as directory:
            paths = reporting.write_reports(self._small_suite(), Path(directory))
            with paths["csv"].open(newline="", encoding="utf-8") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[0], reporting.CSV_COLUMNS)
            body = rows[1:]
            identifiers = {row[0] for row in body}
            self.assertEqual(identifiers, set(_FAST_IDS))
            algorithms = {row[2] for row in body}
            self.assertEqual(algorithms, set(bench.ALGORITHMS))
            statuses = {row[3] for row in body}
            self.assertIn(bench.STATUS_SOLVED, statuses)
            self.assertIn(bench.STATUS_INVALID_INPUT, statuses)
            self.assertIn(bench.STATUS_UNSOLVABLE, statuses)

    def test_markdown_contains_dataset_and_sections(self):
        with TemporaryDirectory() as directory:
            paths = reporting.write_reports(self._small_suite(), Path(directory))
            text = paths["markdown"].read_text(encoding="utf-8")
            for token in (
                "# Sudoku solver benchmark report",
                "## Dataset",
                "## Methodology and metric definitions",
                "## Detailed results",
                "## Limitations",
            ):
                self.assertIn(token, text)
            for identifier in _FAST_IDS:
                self.assertIn(identifier, text)

    def test_execution_time_svg_has_labels_and_data(self):
        with TemporaryDirectory() as directory:
            paths = reporting.write_reports(self._small_suite(), Path(directory))
            svg = paths["execution_time_svg"].read_text(encoding="utf-8")
            self.assertTrue(svg.startswith("<svg"))
            self.assertTrue(svg.rstrip().endswith("</svg>"))
            self.assertIn("Median solver execution time", svg)
            self.assertIn("easy_classic", svg)
            for name in bench.ALGORITHMS:
                self.assertIn(name, svg)

    def test_search_effort_svg_has_metrics(self):
        with TemporaryDirectory() as directory:
            paths = reporting.write_reports(self._small_suite(), Path(directory))
            svg = paths["search_effort_svg"].read_text(encoding="utf-8")
            self.assertIn("Recursive calls", svg)
            self.assertIn("Attempted assignments", svg)
            self.assertIn("Backtracks", svg)
            self.assertTrue(svg.rstrip().endswith("</svg>"))

    def test_rerun_regenerates_instead_of_reusing_stale_values(self):
        with TemporaryDirectory() as directory:
            target = Path(directory)
            reporting.write_reports(self._small_suite(repetitions=1), target)
            # Overwrite with a suite that used a different repetition count.
            reporting.write_reports(self._small_suite(repetitions=2), target)
            with (target / reporting.RESULTS_CSV).open(
                newline="", encoding="utf-8"
            ) as handle:
                rows = list(csv.reader(handle))
            repetition_column = rows[0].index("repetitions")
            solved_rows = [row for row in rows[1:] if row[3] == bench.STATUS_SOLVED]
            self.assertTrue(solved_rows)
            self.assertTrue(all(row[repetition_column] == "2" for row in solved_rows))


class DjangoIndependenceTests(SimpleTestCase):
    """The benchmark service must work without Django importable."""

    def test_benchmark_with_django_import_blocked(self):
        project_root = Path(__file__).resolve().parents[2]
        code = textwrap.dedent(
            """
            import sys

            class _BlockDjango:
                def find_spec(self, name, path=None, target=None):
                    if name == "django" or name.startswith("django."):
                        raise ImportError("django import blocked")
                    return None

            sys.meta_path.insert(0, _BlockDjango())

            from sudoku.services.benchmark import benchmark_puzzle
            from sudoku.utils.puzzles import get_puzzle

            result = benchmark_puzzle(get_puzzle("easy_classic"), repetitions=1)
            assert all(o.status == "solved" for o in result.outcomes), result
            assert "django" not in sys.modules, "Django was imported"
            print("IMPORT_OK")
            """
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("IMPORT_OK", completed.stdout)
