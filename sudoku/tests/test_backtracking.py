"""Tests for the basic recursive backtracking solver ``sudoku.ai.backtracking``."""

from __future__ import annotations

import copy
import subprocess
import sys
import textwrap
from pathlib import Path

from django.test import SimpleTestCase

from sudoku.ai.backtracking import SolverResult, solve_backtracking
from sudoku.ai.constraints import get_candidates
from sudoku.tests.fixtures import (
    EMPTY_GRID,
    PUZZLE,
    UNSOLVABLE_NO_DUPLICATES,
    VALID_SOLUTION,
)
from sudoku.utils.validation import (
    SudokuValidationError,
    is_complete,
    is_valid_grid,
    is_valid_solution,
)


class SuccessfulSolveTests(SimpleTestCase):
    """The solver finds and returns a correct solution."""

    def test_known_easy_puzzle_is_solved(self):
        result = solve_backtracking(PUZZLE)
        self.assertTrue(result.solved)
        self.assertEqual(result.solution, VALID_SOLUTION)

    def test_returned_solution_satisfies_all_rules(self):
        result = solve_backtracking(PUZZLE)
        self.assertTrue(is_complete(result.solution))
        self.assertTrue(is_valid_solution(PUZZLE, result.solution))

    def test_every_original_clue_is_preserved(self):
        result = solve_backtracking(PUZZLE)
        for row in range(9):
            for col in range(9):
                clue = PUZZLE[row][col]
                if clue != 0:
                    self.assertEqual(result.solution[row][col], clue)

    def test_empty_grid_is_solved(self):
        result = solve_backtracking(EMPTY_GRID)
        self.assertTrue(result.solved)
        self.assertTrue(is_valid_solution(EMPTY_GRID, result.solution))


class AlreadyCompleteTests(SimpleTestCase):
    """An already-complete valid grid is accepted unchanged."""

    def test_valid_complete_grid_is_accepted(self):
        result = solve_backtracking(VALID_SOLUTION)
        self.assertTrue(result.solved)
        self.assertEqual(result.solution, VALID_SOLUTION)

    def test_valid_complete_grid_statistics(self):
        result = solve_backtracking(VALID_SOLUTION)
        self.assertEqual(result.recursive_calls, 1)
        self.assertEqual(result.attempted_assignments, 0)
        self.assertEqual(result.backtracks, 0)


class UnsolvableTests(SimpleTestCase):
    """A valid but unsolvable puzzle returns solved=False and solution=None."""

    def setUp(self):
        # Verify the fixture's properties instead of assuming unsolvability.
        self.assertTrue(is_valid_grid(UNSOLVABLE_NO_DUPLICATES))
        self.assertFalse(is_complete(UNSOLVABLE_NO_DUPLICATES))
        self.assertEqual(get_candidates(UNSOLVABLE_NO_DUPLICATES, 0, 0), [])

    def test_unsolvable_puzzle_reports_failure(self):
        result = solve_backtracking(UNSOLVABLE_NO_DUPLICATES)
        self.assertFalse(result.solved)
        self.assertIsNone(result.solution)

    def test_unsolvable_puzzle_metrics_are_deterministic(self):
        result = solve_backtracking(UNSOLVABLE_NO_DUPLICATES)
        # The first empty cell has no candidates, so only the initial recursive
        # call happens and nothing is assigned.
        self.assertEqual(result.recursive_calls, 1)
        self.assertEqual(result.attempted_assignments, 0)
        self.assertEqual(result.backtracks, 0)


class InputSafetyTests(SimpleTestCase):
    """The caller's grid is never modified and bad input is rejected."""

    def test_input_unchanged_after_successful_solve(self):
        original = copy.deepcopy(PUZZLE)
        solve_backtracking(PUZZLE)
        self.assertEqual(PUZZLE, original)

    def test_input_unchanged_after_unsolvable_result(self):
        original = copy.deepcopy(UNSOLVABLE_NO_DUPLICATES)
        solve_backtracking(UNSOLVABLE_NO_DUPLICATES)
        self.assertEqual(UNSOLVABLE_NO_DUPLICATES, original)

    def test_duplicate_initial_clues_are_rejected(self):
        grid = copy.deepcopy(EMPTY_GRID)
        grid[0][0] = 5
        grid[0][8] = 5
        with self.assertRaises(SudokuValidationError):
            solve_backtracking(grid)

    def test_malformed_grid_is_rejected(self):
        with self.assertRaises(SudokuValidationError):
            solve_backtracking(None)

        too_few_rows = [row[:] for row in VALID_SOLUTION[:8]]
        with self.assertRaises(SudokuValidationError):
            solve_backtracking(too_few_rows)

        bad_cell = copy.deepcopy(EMPTY_GRID)
        bad_cell[0][0] = "5"
        with self.assertRaises(SudokuValidationError):
            solve_backtracking(bad_cell)

    def test_duplicate_clue_error_is_not_reported_as_unsolvable(self):
        grid = copy.deepcopy(EMPTY_GRID)
        grid[0][0] = 7
        grid[0][1] = 7
        # Must raise, not silently return solved=False.
        with self.assertRaises(SudokuValidationError):
            solve_backtracking(grid)


class MetricsTests(SimpleTestCase):
    """Performance counters behave as documented."""

    VALID_INPUTS = (PUZZLE, EMPTY_GRID, VALID_SOLUTION, UNSOLVABLE_NO_DUPLICATES)

    def test_recursive_calls_at_least_one(self):
        for grid in self.VALID_INPUTS:
            with self.subTest(grid=grid):
                result = solve_backtracking(grid)
                self.assertGreaterEqual(result.recursive_calls, 1)

    def test_counters_are_non_negative(self):
        for grid in self.VALID_INPUTS:
            with self.subTest(grid=grid):
                result = solve_backtracking(grid)
                self.assertGreaterEqual(result.attempted_assignments, 0)
                self.assertGreaterEqual(result.backtracks, 0)

    def test_execution_time_is_non_negative(self):
        for grid in self.VALID_INPUTS:
            with self.subTest(grid=grid):
                result = solve_backtracking(grid)
                self.assertGreaterEqual(result.execution_time_ms, 0.0)

    def test_puzzle_requiring_search_records_backtracks(self):
        result = solve_backtracking(PUZZLE)
        self.assertTrue(result.solved)
        self.assertGreater(result.backtracks, 0)
        self.assertGreater(result.attempted_assignments, 0)

    def test_result_is_a_solver_result_instance(self):
        self.assertIsInstance(solve_backtracking(PUZZLE), SolverResult)


class DjangoIndependenceTests(SimpleTestCase):
    """The solver must work without Django importable."""

    def test_solve_with_django_import_blocked(self):
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

            import sudoku.ai.backtracking as backtracking

            grid = [
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
            result = backtracking.solve_backtracking(grid)
            assert result.solved, "solver failed without Django"
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
