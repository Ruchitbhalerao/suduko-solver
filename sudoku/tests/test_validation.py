"""Tests for grid validation and solution checking in ``sudoku.utils.validation``."""

import copy

from django.test import SimpleTestCase

from sudoku.tests.fixtures import EMPTY_GRID, PUZZLE, VALID_SOLUTION, swap_digits
from sudoku.utils.validation import (
    SudokuValidationError,
    is_complete,
    is_valid_grid,
    is_valid_solution,
    validate_grid,
    validate_grid_structure,
    validate_initial_clues,
    validate_solution,
)


class GridStructureTests(SimpleTestCase):
    """Checks structural validation of the grid itself."""

    def test_accepts_a_valid_solution(self):
        validate_grid_structure(VALID_SOLUTION)

    def test_accepts_a_valid_puzzle(self):
        validate_grid_structure(PUZZLE)

    def test_accepts_an_all_empty_grid(self):
        validate_grid_structure(EMPTY_GRID)

    def test_rejects_none(self):
        with self.assertRaises(SudokuValidationError):
            validate_grid_structure(None)

    def test_rejects_non_list_grid(self):
        with self.assertRaises(SudokuValidationError):
            validate_grid_structure("not a grid")

    def test_rejects_too_few_rows(self):
        with self.assertRaises(SudokuValidationError):
            validate_grid_structure([row[:] for row in VALID_SOLUTION[:8]])

    def test_rejects_too_many_rows(self):
        grid = [row[:] for row in VALID_SOLUTION] + [[0] * 9]
        with self.assertRaises(SudokuValidationError):
            validate_grid_structure(grid)

    def test_rejects_too_few_columns(self):
        grid = [row[:] for row in VALID_SOLUTION]
        grid[0] = VALID_SOLUTION[0][:8]
        with self.assertRaises(SudokuValidationError):
            validate_grid_structure(grid)

    def test_rejects_too_many_columns(self):
        grid = [row[:] for row in VALID_SOLUTION]
        grid[0] = VALID_SOLUTION[0] + [0]
        with self.assertRaises(SudokuValidationError):
            validate_grid_structure(grid)

    def test_rejects_negative_value(self):
        grid = [row[:] for row in VALID_SOLUTION]
        grid[0][0] = -1
        with self.assertRaises(SudokuValidationError):
            validate_grid_structure(grid)

    def test_rejects_value_above_nine(self):
        grid = [row[:] for row in VALID_SOLUTION]
        grid[0][0] = 10
        with self.assertRaises(SudokuValidationError):
            validate_grid_structure(grid)

    def test_rejects_string_value(self):
        grid = [row[:] for row in VALID_SOLUTION]
        grid[0][0] = "5"
        with self.assertRaises(SudokuValidationError):
            validate_grid_structure(grid)

    def test_rejects_float_value(self):
        grid = [row[:] for row in VALID_SOLUTION]
        grid[0][0] = 5.0
        with self.assertRaises(SudokuValidationError):
            validate_grid_structure(grid)

    def test_rejects_boolean_value(self):
        grid = [row[:] for row in VALID_SOLUTION]
        grid[0][0] = True
        with self.assertRaises(SudokuValidationError):
            validate_grid_structure(grid)
        grid[0][0] = False
        with self.assertRaises(SudokuValidationError):
            validate_grid_structure(grid)


class InitialCluesTests(SimpleTestCase):
    """Checks detection of duplicate clues."""

    def test_accepts_a_consistent_puzzle(self):
        validate_initial_clues(PUZZLE)

    def test_detects_duplicate_in_row(self):
        grid = copy.deepcopy(EMPTY_GRID)
        grid[0][0] = 5
        grid[0][8] = 5
        with self.assertRaisesRegex(SudokuValidationError, r"Duplicate clue value 5 in row 1"):
            validate_initial_clues(grid)

    def test_detects_duplicate_in_column(self):
        grid = copy.deepcopy(EMPTY_GRID)
        grid[0][0] = 7
        grid[8][0] = 7
        with self.assertRaisesRegex(SudokuValidationError, r"Duplicate clue value 7 in column 1"):
            validate_initial_clues(grid)

    def test_detects_duplicate_in_subgrid(self):
        grid = copy.deepcopy(EMPTY_GRID)
        grid[0][0] = 3
        grid[2][2] = 3
        with self.assertRaisesRegex(
            SudokuValidationError, r"Duplicate clue value 3 in 3x3 subgrid"
        ):
            validate_initial_clues(grid)

    def test_zero_is_not_treated_as_a_clue(self):
        grid = copy.deepcopy(EMPTY_GRID)
        validate_initial_clues(grid)


class OverallValidationTests(SimpleTestCase):
    """Checks the convenience wrappers ``validate_grid`` / ``is_valid_grid``."""

    def test_validate_grid_accepts_a_good_puzzle(self):
        validate_grid(PUZZLE)

    def test_validate_grid_rejects_a_malformed_grid(self):
        with self.assertRaises(SudokuValidationError):
            validate_grid(None)

    def test_is_valid_grid_returns_bool(self):
        self.assertTrue(is_valid_grid(PUZZLE))
        self.assertFalse(is_valid_grid(None))
        broken = copy.deepcopy(PUZZLE)
        broken[0][0] = 6  # duplicates the 6 already in column 0
        self.assertFalse(is_valid_grid(broken))


class CompletenessTests(SimpleTestCase):
    """Checks the ``is_complete`` predicate."""

    def test_empty_grid_is_not_complete(self):
        self.assertFalse(is_complete(EMPTY_GRID))

    def test_puzzle_is_not_complete(self):
        self.assertFalse(is_complete(PUZZLE))

    def test_solution_is_complete(self):
        self.assertTrue(is_complete(VALID_SOLUTION))

    def test_malformed_grid_raises_rather_than_reporting_incomplete(self):
        with self.assertRaises(SudokuValidationError):
            is_complete(None)


class SolutionValidationTests(SimpleTestCase):
    """Checks full solution verification."""

    def test_accepts_the_true_solution(self):
        validate_solution(PUZZLE, VALID_SOLUTION)
        self.assertTrue(is_valid_solution(PUZZLE, VALID_SOLUTION))

    def test_rejects_an_incomplete_grid(self):
        self.assertFalse(is_valid_solution(PUZZLE, PUZZLE))
        with self.assertRaisesRegex(SudokuValidationError, r"incomplete"):
            validate_solution(PUZZLE, PUZZLE)

    def test_rejects_a_complete_grid_with_duplicates(self):
        broken = copy.deepcopy(VALID_SOLUTION)
        broken[0][3] = 5  # row 0 already has a 5 at column 0
        self.assertFalse(is_valid_solution(PUZZLE, broken))
        with self.assertRaisesRegex(SudokuValidationError, r"violates a Sudoku rule"):
            validate_solution(PUZZLE, broken)

    def test_rejects_a_solution_that_changes_a_clue(self):
        # Swapping two digits yields another valid complete grid, so the rule
        # check passes and only the clue-preservation check can fail.
        alternate = swap_digits(VALID_SOLUTION, 1, 2)
        self.assertFalse(is_valid_solution(PUZZLE, alternate))
        with self.assertRaisesRegex(SudokuValidationError, r"changes the original clue"):
            validate_solution(PUZZLE, alternate)

    def test_solution_preserving_all_clues_is_accepted(self):
        self.assertTrue(is_valid_solution(PUZZLE, VALID_SOLUTION))


class MutationSafetyTests(SimpleTestCase):
    """Confirms no function modifies the grid it is given."""

    def test_validation_functions_do_not_mutate_inputs(self):
        original = copy.deepcopy(PUZZLE)
        solution = copy.deepcopy(VALID_SOLUTION)

        validate_grid_structure(PUZZLE)
        validate_initial_clues(PUZZLE)
        validate_grid(PUZZLE)
        is_complete(PUZZLE)
        validate_solution(PUZZLE, VALID_SOLUTION)
        is_valid_solution(PUZZLE, VALID_SOLUTION)
        is_valid_grid(PUZZLE)

        self.assertEqual(PUZZLE, original)
        self.assertEqual(VALID_SOLUTION, solution)
