"""Tests for random puzzle generation and the ``/api/generate/`` endpoint.

The generator is part of the Django-free AI engine, so its unit tests only use
``SimpleTestCase`` (no database). The API tests mirror the status-code contract
used by ``test_api.py``.
"""

from __future__ import annotations

import json
import random

from django.test import SimpleTestCase
from django.urls import reverse

from sudoku.ai.generator import (
    DEFAULT_DIFFICULTY,
    DIFFICULTIES,
    DIFFICULTY_CLUE_TARGETS,
    MIN_CLUES,
    count_solutions,
    generate_puzzle,
    generate_solution,
    has_unique_solution,
)
from sudoku.ai.solvers import ALGORITHM_RUNNERS
from sudoku.tests.fixtures import EMPTY_GRID, PUZZLE
from sudoku.utils.validation import (
    SudokuValidationError,
    is_complete,
    is_valid_grid,
    is_valid_solution,
)


class GenerateSolutionTests(SimpleTestCase):
    """``generate_solution`` returns complete, valid, varied grids."""

    def test_solution_is_complete_and_valid(self):
        solution = generate_solution(random.Random(1))
        self.assertTrue(is_complete(solution))
        self.assertTrue(is_valid_grid(solution))

    def test_solution_is_reproducible_with_a_seed(self):
        first = generate_solution(random.Random(2026))
        second = generate_solution(random.Random(2026))
        self.assertEqual(first, second)


class CountSolutionsTests(SimpleTestCase):
    """``count_solutions`` counts correctly and never mutates its input."""

    def test_known_puzzle_has_one_solution(self):
        self.assertEqual(count_solutions(PUZZLE), 1)
        self.assertTrue(has_unique_solution(PUZZLE))

    def test_empty_grid_has_more_than_one_solution(self):
        self.assertEqual(count_solutions(EMPTY_GRID, limit=2), 2)
        self.assertFalse(has_unique_solution(EMPTY_GRID))

    def test_input_grid_is_not_mutated(self):
        snapshot = [row[:] for row in PUZZLE]
        count_solutions(PUZZLE, limit=2)
        self.assertEqual(PUZZLE, snapshot)

    def test_malformed_grid_is_rejected(self):
        conflicting = [row[:] for row in PUZZLE]
        conflicting[0][2] = 5  # row 0 already has a 5
        with self.assertRaises(SudokuValidationError):
            count_solutions(conflicting)

    def test_non_positive_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            count_solutions(PUZZLE, limit=0)


class GeneratePuzzleTests(SimpleTestCase):
    """``generate_puzzle`` produces valid puzzles with unique solutions."""

    def test_puzzle_is_valid_and_incomplete(self):
        generated = generate_puzzle("easy", rng=random.Random(3))
        self.assertTrue(is_valid_grid(generated.puzzle))
        self.assertFalse(is_complete(generated.puzzle))
        self.assertGreater(generated.clues, 0)

    def test_puzzle_has_exactly_one_solution(self):
        generated = generate_puzzle("medium", rng=random.Random(4))
        self.assertTrue(generated.unique)
        self.assertEqual(count_solutions(generated.puzzle, limit=2), 1)

    def test_solution_is_a_valid_solution_of_the_puzzle(self):
        generated = generate_puzzle("hard", rng=random.Random(5))
        for runner in ALGORITHM_RUNNERS.values():
            result = runner(generated.puzzle)
            self.assertTrue(result.solved)
            self.assertEqual(result.solution, generated.solution)
            break  # one solver is enough; all three share the same solution

    def test_clue_count_matches_reported_count(self):
        generated = generate_puzzle("medium", rng=random.Random(6))
        counted = sum(1 for row in generated.puzzle for cell in row if cell != 0)
        self.assertEqual(counted, generated.clues)

    def test_easier_puzzles_keep_at_least_as_many_clues(self):
        easy = generate_puzzle("easy", rng=random.Random(11))
        hard = generate_puzzle("hard", rng=random.Random(11))
        self.assertGreaterEqual(easy.clues, hard.clues)
        self.assertGreaterEqual(hard.clues, MIN_CLUES)

    def test_default_difficulty_matches_target(self):
        generated = generate_puzzle(rng=random.Random(12))
        self.assertEqual(generated.difficulty, DEFAULT_DIFFICULTY)
        self.assertLessEqual(generated.clues, DIFFICULTY_CLUE_TARGETS[DEFAULT_DIFFICULTY])

    def test_generation_is_reproducible_with_a_seed(self):
        first = generate_puzzle("medium", rng=random.Random(20261016))
        second = generate_puzzle("medium", rng=random.Random(20261016))
        self.assertEqual(first.puzzle, second.puzzle)
        self.assertEqual(first.solution, second.solution)

    def test_unknown_difficulty_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_puzzle("impossible")

    def test_out_of_range_min_clues_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_puzzle("easy", min_clues=5)
        with self.assertRaises(ValueError):
            generate_puzzle("easy", min_clues=100)


class GenerateEndpointTests(SimpleTestCase):
    """``POST /api/generate/`` behaviour."""

    generate_url = reverse("sudoku:api_generate")

    def post_json(self, payload):
        return self.client.post(
            self.generate_url, data=json.dumps(payload), content_type="application/json"
        )

    def test_generate_url_resolves(self):
        self.assertEqual(reverse("sudoku:api_generate"), "/api/generate/")

    def test_generates_a_valid_unique_puzzle(self):
        response = self.post_json({"difficulty": "easy"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "generated")
        self.assertEqual(body["difficulty"], "easy")
        self.assertTrue(body["unique"])
        self.assertEqual(len(body["puzzle"]), 9)
        self.assertTrue(is_valid_grid(body["puzzle"]))
        self.assertEqual(count_solutions(body["puzzle"], limit=2), 1)
        self.assertNotIn("solution", body)

    def test_default_difficulty_is_medium(self):
        response = self.post_json({})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["difficulty"], DEFAULT_DIFFICULTY)

    def test_include_solution_returns_a_valid_solution(self):
        response = self.post_json({"difficulty": "medium", "include_solution": True})
        body = response.json()
        self.assertIn("solution", body)
        self.assertTrue(is_complete(body["solution"]))
        self.assertTrue(is_valid_solution(body["puzzle"], body["solution"]))

    def test_every_difficulty_is_accepted(self):
        for difficulty in DIFFICULTIES:
            with self.subTest(difficulty=difficulty):
                response = self.post_json({"difficulty": difficulty})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["difficulty"], difficulty)

    def test_unsupported_difficulty_is_400(self):
        response = self.post_json({"difficulty": "nightmare"})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["error"]["code"], "unsupported_difficulty")

    def test_non_string_difficulty_is_400(self):
        response = self.post_json({"difficulty": 3})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_request")

    def test_non_boolean_include_solution_is_400(self):
        response = self.post_json({"include_solution": "yes"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_request")

    def test_malformed_json_is_400(self):
        response = self.client.post(
            self.generate_url, data="{not valid json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "malformed_json")

    def test_non_json_content_type_is_415(self):
        response = self.client.post(
            self.generate_url, data=json.dumps({}), content_type="text/plain"
        )
        self.assertEqual(response.status_code, 415)

    def test_get_method_not_allowed(self):
        response = self.client.get(self.generate_url)
        self.assertEqual(response.status_code, 405)
