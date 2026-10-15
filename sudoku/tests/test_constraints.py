"""Tests for the AI constraint primitives in ``sudoku.ai.constraints``."""

from django.test import SimpleTestCase

from sudoku.ai.constraints import find_empty_cell, get_candidates, is_valid_move
from sudoku.tests.fixtures import EMPTY_GRID, PUZZLE, VALID_SOLUTION


class IsValidMoveTests(SimpleTestCase):
    """Checks legality of individual placements."""

    def test_any_value_is_valid_in_an_empty_grid(self):
        for row in range(9):
            for col in range(9):
                self.assertTrue(is_valid_move(EMPTY_GRID, row, col, 5))

    def test_accepts_a_legal_placement(self):
        # Cell (0, 2) is empty and 4 is absent from its row, column and box.
        self.assertTrue(is_valid_move(PUZZLE, 0, 2, 4))

    def test_rejects_duplicate_in_row(self):
        # Row 0 already contains a 5 at column 0.
        self.assertFalse(is_valid_move(PUZZLE, 0, 2, 5))

    def test_rejects_duplicate_in_column(self):
        # Column 0 already contains a 6 at row 1.
        self.assertFalse(is_valid_move(PUZZLE, 2, 0, 6))

    def test_rejects_duplicate_in_subgrid(self):
        # The top-left 3x3 box already contains a 5 at (0, 0).
        self.assertFalse(is_valid_move(PUZZLE, 2, 2, 5))

    def test_uses_zero_based_indices(self):
        self.assertTrue(is_valid_move(EMPTY_GRID, 0, 0, 1))
        self.assertTrue(is_valid_move(EMPTY_GRID, 8, 8, 9))
        self.assertTrue(is_valid_move(EMPTY_GRID, 8, 0, 9))

    def test_filled_cell_does_not_conflict_with_its_own_value(self):
        # (0, 0) holds 5; asking about 5 there must not self-conflict.
        self.assertTrue(is_valid_move(VALID_SOLUTION, 0, 0, 5))

    def test_invalid_row_raises(self):
        for bad_row in (-1, 9, "0", 1.0, True, None):
            with self.assertRaises(ValueError):
                is_valid_move(EMPTY_GRID, bad_row, 0, 5)

    def test_invalid_column_raises(self):
        for bad_col in (-1, 9, "0", 1.0, True, None):
            with self.assertRaises(ValueError):
                is_valid_move(EMPTY_GRID, 0, bad_col, 5)

    def test_invalid_value_raises(self):
        for bad_value in (0, -1, 10, "5", 5.0, True, None):
            with self.assertRaises(ValueError):
                is_valid_move(EMPTY_GRID, 0, 0, bad_value)

    def test_zero_is_never_a_valid_value(self):
        with self.assertRaises(ValueError):
            is_valid_move(EMPTY_GRID, 0, 0, 0)


class GetCandidatesTests(SimpleTestCase):
    """Checks candidate generation for a cell."""

    def test_excludes_row_column_and_box_values(self):
        # (0, 2) in PUZZLE: row {3,5,7}, column {8}, box {3,5,6,8,9}.
        self.assertEqual(get_candidates(PUZZLE, 0, 2), [1, 2, 4])

    def test_candidates_are_unique_ascending_and_in_range(self):
        for row in range(9):
            for col in range(9):
                candidates = get_candidates(PUZZLE, row, col)
                self.assertEqual(candidates, sorted(set(candidates)))
                self.assertTrue(all(1 <= value <= 9 for value in candidates))
                self.assertNotIn(0, candidates)

    def test_cell_with_no_legal_candidates_is_empty(self):
        grid = [row[:] for row in EMPTY_GRID]
        grid[0] = [1, 2, 3, 4, 5, 6, 7, 8, 0]
        grid[1][8] = 9
        self.assertEqual(get_candidates(grid, 0, 8), [])

    def test_invalid_indices_raise(self):
        with self.assertRaises(ValueError):
            get_candidates(EMPTY_GRID, -1, 0)
        with self.assertRaises(ValueError):
            get_candidates(EMPTY_GRID, 0, 9)


class FindEmptyCellTests(SimpleTestCase):
    """Checks discovery of the next empty cell."""

    def test_finds_first_empty_cell_in_row_major_order(self):
        self.assertEqual(find_empty_cell(EMPTY_GRID), (0, 0))
        self.assertEqual(find_empty_cell(PUZZLE), (0, 2))

    def test_returns_none_for_a_complete_grid(self):
        self.assertIsNone(find_empty_cell(VALID_SOLUTION))

    def test_finds_a_later_empty_cell(self):
        grid = [row[:] for row in VALID_SOLUTION]
        grid[4][5] = 0
        self.assertEqual(find_empty_cell(grid), (4, 5))
