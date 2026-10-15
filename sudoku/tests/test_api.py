"""Phase 7 (part 1) tests for the Sudoku JSON API.

These tests exercise the endpoints at the HTTP level through Django's test
client. They never assert exact execution times and never assume one algorithm
is faster than another. Because no database is used, they extend
``SimpleTestCase``.

Status-code contract under test
-------------------------------
* 200 -- valid grid (``/api/validate/``) or a solve attempt with an answer,
  including a valid-but-unsolvable puzzle.
* 400 -- malformed JSON, missing/invalid request fields, unsupported algorithm.
* 405 -- wrong HTTP method.
* 415 -- non-JSON content type.
* 422 -- a well-formed request whose grid fails Sudoku validation.

The distinction "invalid input (422) vs valid unsolvable (200)" is asserted
directly.
"""

from __future__ import annotations

import json
from unittest import mock

from django.test import SimpleTestCase
from django.urls import reverse

from sudoku import api_views
from sudoku.ai.backtracking import SolverError
from sudoku.ai.solvers import ALGORITHMS, DEFAULT_ALGORITHM
from sudoku.utils.validation import is_valid_solution
from sudoku.tests.fixtures import (
    EMPTY_GRID,
    PUZZLE,
    UNSOLVABLE_NO_DUPLICATES,
    VALID_SOLUTION,
)


def _json_content_type(response) -> str:
    """Return just the media type of a response's Content-Type header."""
    return response.headers["Content-Type"].split(";")[0].strip()


class ApiTestBase(SimpleTestCase):
    """Shared helpers for posting JSON and reading responses."""

    validate_url = reverse("sudoku:api_validate")
    solve_url = reverse("sudoku:api_solve")

    def post_json(self, url, payload):
        return self.client.post(
            url, data=json.dumps(payload), content_type="application/json"
        )

    def body(self, response):
        return json.loads(response.content)


class UrlAndPageRegressionTests(ApiTestBase):
    """Routing is correct and the Phase 1 page still works."""

    def test_validate_url_resolves(self):
        self.assertEqual(reverse("sudoku:api_validate"), "/api/validate/")

    def test_solve_url_resolves(self):
        self.assertEqual(reverse("sudoku:api_solve"), "/api/solve/")

    def test_placeholder_page_still_works(self):
        response = self.client.get(reverse("sudoku:placeholder"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI-Based Sudoku Solver")

    def test_placeholder_url_still_resolves(self):
        self.assertEqual(reverse("sudoku:placeholder"), "/")


class ValidateEndpointTests(ApiTestBase):
    """``POST /api/validate/`` behaviour."""

    def test_valid_puzzle_is_reported_valid(self):
        response = self.post_json(self.validate_url, {"grid": PUZZLE})
        self.assertEqual(response.status_code, 200)
        body = self.body(response)
        self.assertTrue(body["valid"])
        self.assertEqual(body["status"], "valid")
        self.assertEqual(_json_content_type(response), "application/json")

    def test_empty_grid_is_valid(self):
        response = self.post_json(self.validate_url, {"grid": EMPTY_GRID})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.body(response)["valid"])

    def test_already_complete_grid_is_valid(self):
        response = self.post_json(self.validate_url, {"grid": VALID_SOLUTION})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.body(response)["valid"])

    def test_unsolvable_but_valid_puzzle_is_reported_valid(self):
        # The heart of the requirement: no solution does not mean invalid input.
        response = self.post_json(
            self.validate_url, {"grid": UNSOLVABLE_NO_DUPLICATES}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.body(response)["valid"])

    def test_duplicate_clues_rejected_with_422(self):
        grid = [row[:] for row in PUZZLE]
        grid[0][2] = 5  # row 0 already contains a 5 at column 0
        response = self.post_json(self.validate_url, {"grid": grid})
        self.assertEqual(response.status_code, 422)
        body = self.body(response)
        self.assertFalse(body["valid"])
        self.assertEqual(body["status"], "invalid_grid")
        self.assertEqual(body["error"]["code"], "invalid_grid")
        self.assertIn("Duplicate", body["error"]["message"])

    def test_wrong_row_count_rejected_with_422(self):
        grid = [[0] * 9 for _ in range(8)]
        response = self.post_json(self.validate_url, {"grid": grid})
        self.assertEqual(response.status_code, 422)
        self.assertIn("rows", self.body(response)["error"]["message"])

    def test_wrong_cell_count_rejected_with_422(self):
        grid = [row[:] for row in EMPTY_GRID]
        grid[0] = grid[0][:-1]  # 8 cells in row 1
        response = self.post_json(self.validate_url, {"grid": grid})
        self.assertEqual(response.status_code, 422)
        self.assertIn("cells", self.body(response)["error"]["message"])

    def test_out_of_range_cell_rejected_with_422(self):
        grid = [row[:] for row in PUZZLE]
        grid[0][2] = 10
        response = self.post_json(self.validate_url, {"grid": grid})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.body(response)["error"]["code"], "invalid_grid")

    def test_non_integer_cell_rejected_with_422(self):
        grid = [row[:] for row in PUZZLE]
        grid[0][2] = "five"
        response = self.post_json(self.validate_url, {"grid": grid})
        self.assertEqual(response.status_code, 422)

    def test_boolean_cell_rejected_with_422(self):
        grid = [row[:] for row in PUZZLE]
        grid[0][2] = True  # bool is not a valid Sudoku value
        response = self.post_json(self.validate_url, {"grid": grid})
        self.assertEqual(response.status_code, 422)

    def test_non_list_grid_rejected_with_422(self):
        response = self.post_json(self.validate_url, {"grid": "not a grid"})
        self.assertEqual(response.status_code, 422)

    def test_missing_grid_field_is_400(self):
        response = self.post_json(self.validate_url, {})
        self.assertEqual(response.status_code, 400)
        body = self.body(response)
        self.assertEqual(body["error"]["code"], "invalid_request")
        self.assertIn("grid", body["error"]["message"])

    def test_malformed_json_is_400(self):
        response = self.client.post(
            self.validate_url, data="{not valid json", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["error"]["code"], "malformed_json")

    def test_json_top_level_must_be_object(self):
        response = self.client.post(
            self.validate_url, data=json.dumps([1, 2, 3]), content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["error"]["code"], "invalid_request")

    def test_non_json_content_type_is_415(self):
        response = self.client.post(
            self.validate_url, data=json.dumps({"grid": PUZZLE}), content_type="text/plain"
        )
        self.assertEqual(response.status_code, 415)
        self.assertEqual(
            self.body(response)["error"]["code"], "unsupported_media_type"
        )

    def test_algorithm_field_is_ignored_by_validate(self):
        # Validation never solves, so even a bogus algorithm must not matter.
        response = self.post_json(
            self.validate_url, {"grid": PUZZLE, "algorithm": "not-a-real-algorithm"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.body(response)["valid"])

    def test_get_method_not_allowed(self):
        response = self.client.get(self.validate_url)
        self.assertEqual(response.status_code, 405)


class SolveEndpointTests(ApiTestBase):
    """``POST /api/solve/`` behaviour."""

    def test_solves_with_each_algorithm(self):
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                response = self.post_json(
                    self.solve_url, {"grid": PUZZLE, "algorithm": algorithm}
                )
                self.assertEqual(response.status_code, 200)
                body = self.body(response)
                self.assertTrue(body["solved"])
                self.assertEqual(body["status"], "solved")
                self.assertEqual(body["algorithm"], algorithm)

    def test_solution_is_independently_valid(self):
        response = self.post_json(
            self.solve_url, {"grid": PUZZLE, "algorithm": "backtracking"}
        )
        solution = self.body(response)["solution"]
        self.assertTrue(is_valid_solution(PUZZLE, solution))

    def test_solution_preserves_every_original_clue(self):
        response = self.post_json(self.solve_url, {"grid": PUZZLE, "algorithm": "mrv"})
        solution = self.body(response)["solution"]
        for row in range(9):
            for col in range(9):
                if PUZZLE[row][col] != 0:
                    self.assertEqual(solution[row][col], PUZZLE[row][col])

    def test_solved_response_returns_known_solution(self):
        response = self.post_json(
            self.solve_url, {"grid": PUZZLE, "algorithm": "mrv_forward_checking"}
        )
        self.assertEqual(self.body(response)["solution"], VALID_SOLUTION)

    def test_default_algorithm_when_omitted(self):
        response = self.post_json(self.solve_url, {"grid": PUZZLE})
        self.assertEqual(response.status_code, 200)
        body = self.body(response)
        self.assertEqual(body["algorithm"], DEFAULT_ALGORITHM)
        self.assertTrue(body["solved"])

    def test_already_complete_grid_solves_without_assignments(self):
        response = self.post_json(
            self.solve_url, {"grid": VALID_SOLUTION, "algorithm": "backtracking"}
        )
        body = self.body(response)
        self.assertTrue(body["solved"])
        self.assertEqual(body["solution"], VALID_SOLUTION)
        self.assertEqual(body["metrics"]["attempted_assignments"], 0)
        self.assertEqual(body["metrics"]["backtracks"], 0)

    def test_unsolvable_puzzle_returns_200_and_unsolvable_status(self):
        response = self.post_json(
            self.solve_url,
            {"grid": UNSOLVABLE_NO_DUPLICATES, "algorithm": "backtracking"},
        )
        self.assertEqual(response.status_code, 200)
        body = self.body(response)
        self.assertFalse(body["solved"])
        self.assertEqual(body["status"], "unsolvable")
        self.assertIsNone(body["solution"])

    def test_invalid_grid_is_422_and_distinct_from_unsolvable(self):
        grid = [row[:] for row in PUZZLE]
        grid[0][2] = 5  # duplicate clue -> invalid input, not unsolvable
        response = self.post_json(
            self.solve_url, {"grid": grid, "algorithm": "backtracking"}
        )
        self.assertEqual(response.status_code, 422)
        body = self.body(response)
        self.assertFalse(body["solved"])
        self.assertEqual(body["status"], "invalid_grid")
        self.assertNotEqual(body.get("status"), "unsolvable")

    def test_unsupported_algorithm_is_400(self):
        response = self.post_json(
            self.solve_url, {"grid": PUZZLE, "algorithm": "dancing_links"}
        )
        self.assertEqual(response.status_code, 400)
        body = self.body(response)
        self.assertEqual(body["error"]["code"], "unsupported_algorithm")
        self.assertIn("dancing_links", body["error"]["message"])
        self.assertIn("mrv", body["error"]["message"])

    def test_non_string_algorithm_is_400(self):
        response = self.post_json(self.solve_url, {"grid": PUZZLE, "algorithm": 5})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["error"]["code"], "invalid_request")

    def test_missing_grid_is_400(self):
        response = self.post_json(self.solve_url, {"algorithm": "mrv"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["error"]["code"], "invalid_request")

    def test_malformed_json_is_400(self):
        response = self.client.post(
            self.solve_url, data="{", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.body(response)["error"]["code"], "malformed_json")

    def test_non_json_content_type_is_415(self):
        response = self.client.post(
            self.solve_url,
            data=json.dumps({"grid": PUZZLE}),
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(response.status_code, 415)

    def test_get_method_not_allowed(self):
        response = self.client.get(self.solve_url)
        self.assertEqual(response.status_code, 405)

    def test_response_content_type_is_json(self):
        response = self.post_json(self.solve_url, {"grid": PUZZLE})
        self.assertEqual(_json_content_type(response), "application/json")

    def test_metrics_are_present_and_correctly_typed(self):
        response = self.post_json(
            self.solve_url, {"grid": PUZZLE, "algorithm": "backtracking"}
        )
        metrics = self.body(response)["metrics"]
        self.assertEqual(
            set(metrics),
            {
                "recursive_calls",
                "attempted_assignments",
                "backtracks",
                "execution_time_ms",
            },
        )
        self.assertIsInstance(metrics["recursive_calls"], int)
        self.assertIsInstance(metrics["attempted_assignments"], int)
        self.assertIsInstance(metrics["backtracks"], int)
        self.assertIsInstance(metrics["execution_time_ms"], float)
        self.assertGreaterEqual(metrics["recursive_calls"], 1)
        self.assertGreaterEqual(metrics["execution_time_ms"], 0.0)

    def test_metrics_reported_even_when_unsolvable(self):
        response = self.post_json(
            self.solve_url, {"grid": UNSOLVABLE_NO_DUPLICATES}
        )
        metrics = self.body(response)["metrics"]
        self.assertIsInstance(metrics["recursive_calls"], int)
        self.assertIsInstance(metrics["execution_time_ms"], float)

    def test_request_payload_grid_is_not_mutated(self):
        payload = {"grid": [row[:] for row in PUZZLE], "algorithm": "mrv"}
        expected = [row[:] for row in PUZZLE]
        self.post_json(self.solve_url, payload)
        self.assertEqual(payload["grid"], expected)


class InternalErrorHandlingTests(ApiTestBase):
    """Internal faults stay internal: generic 500, no leaked details."""

    def test_solver_error_returns_generic_500(self):
        def boom(_grid):
            raise SolverError("secret internal detail")

        with mock.patch.dict(api_views.ALGORITHM_RUNNERS, {"mrv": boom}):
            with self.assertLogs("sudoku.api_views", level="ERROR"):
                response = self.post_json(
                    self.solve_url, {"grid": PUZZLE, "algorithm": "mrv"}
                )

        self.assertEqual(response.status_code, 500)
        body = self.body(response)
        self.assertFalse(body["solved"])
        self.assertEqual(body["error"]["code"], "internal_error")
        self.assertNotIn("secret internal detail", json.dumps(body))
        self.assertNotIn("Traceback", json.dumps(body))

    def test_unexpected_exception_returns_generic_500(self):
        def boom(_grid):
            raise RuntimeError("boom")

        with mock.patch.dict(api_views.ALGORITHM_RUNNERS, {"backtracking": boom}):
            with self.assertLogs("sudoku.api_views", level="ERROR"):
                response = self.post_json(
                    self.solve_url, {"grid": PUZZLE, "algorithm": "backtracking"}
                )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.body(response)["error"]["code"], "internal_error")

    def test_unexpected_exception_is_not_reported_as_unsolvable(self):
        def boom(_grid):
            raise RuntimeError("boom")

        with mock.patch.dict(api_views.ALGORITHM_RUNNERS, {"mrv": boom}):
            with self.assertLogs("sudoku.api_views", level="ERROR"):
                response = self.post_json(
                    self.solve_url, {"grid": PUZZLE, "algorithm": "mrv"}
                )

        self.assertNotEqual(self.body(response)["status"], "unsolvable")
        self.assertEqual(response.status_code, 500)
