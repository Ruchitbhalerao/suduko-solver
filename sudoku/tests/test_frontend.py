"""Phase 7 (part 2) frontend integration tests.

These tests use Django's test client and static-file finders. They check that the
home page renders the Sudoku interface, that the required controls, labels,
algorithm identifiers, and static assets are present, that the page points at the
existing API endpoints, and that the example puzzle really is accepted and
solvable by every algorithm through the real API.

There is no browser automation available in this environment (neither Selenium
nor Playwright is installed, and adding one is out of scope), so the JavaScript
itself is checked statically and a manual browser checklist is provided in the
README. Behavioural API coverage lives in ``test_api.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase
from django.urls import reverse

# The example puzzle the frontend loads (must match EXAMPLE_PUZZLE in app.js).
EXAMPLE_PUZZLE = [
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

ALGORITHM_IDENTIFIERS = ("backtracking", "mrv", "mrv_forward_checking")


def _read_static(relative_path: str) -> str:
    found = finders.find(relative_path)
    assert found is not None, f"Static asset not found: {relative_path}"
    return Path(found).read_text(encoding="utf-8")


class HomePageTests(SimpleTestCase):
    """The home page renders and contains the required interface."""

    def setUp(self):
        self.response = self.client.get(reverse("sudoku:placeholder"))

    def test_home_page_returns_200(self):
        self.assertEqual(self.response.status_code, 200)

    def test_home_page_uses_expected_template(self):
        self.assertTemplateUsed(self.response, "sudoku/placeholder.html")

    def test_home_page_shows_project_title(self):
        self.assertContains(self.response, "AI-Based Sudoku Solver")

    def test_home_page_has_grid_container(self):
        self.assertContains(self.response, 'id="sudoku-grid"')
        self.assertContains(self.response, 'role="grid"')

    def test_home_page_has_required_controls(self):
        for element_id in (
            "solve-button",
            "validate-button",
            "clear-button",
            "load-example-button",
            "algorithm",
        ):
            with self.subTest(element=element_id):
                self.assertContains(self.response, f'id="{element_id}"')

    def test_home_page_has_status_and_results_regions(self):
        self.assertContains(self.response, 'id="status"')
        self.assertContains(self.response, 'role="status"')
        self.assertContains(self.response, 'id="results"')
        self.assertContains(self.response, 'id="stale-note"')

    def test_all_algorithm_identifiers_are_offered(self):
        for identifier in ALGORITHM_IDENTIFIERS:
            with self.subTest(algorithm=identifier):
                self.assertContains(self.response, f'value="{identifier}"')

    def test_page_references_the_api_endpoints(self):
        self.assertContains(self.response, 'data-validate-url="/api/validate/"')
        self.assertContains(self.response, 'data-solve-url="/api/solve/"')

    def test_page_references_static_assets(self):
        self.assertContains(self.response, "sudoku/css/styles.css")
        self.assertContains(self.response, "sudoku/js/app.js")

    def test_page_explains_all_three_algorithms(self):
        self.assertContains(self.response, "Backtracking")
        self.assertContains(self.response, "Minimum Remaining Values")
        self.assertContains(self.response, "Forward Checking")

    def test_page_has_accessible_skip_link(self):
        self.assertContains(self.response, "Skip to the Sudoku grid")


class StaticAssetTests(SimpleTestCase):
    """Static files exist and contain the expected frontend hooks."""

    def test_css_asset_exists(self):
        self.assertIsNotNone(finders.find("sudoku/css/styles.css"))

    def test_js_asset_exists(self):
        self.assertIsNotNone(finders.find("sudoku/js/app.js"))

    def test_css_defines_board_and_cell_states(self):
        css = _read_static("sudoku/css/styles.css")
        for selector in (".sudoku-grid", ".cell.clue", ".cell.solved",
                         ".cell.entered", ":focus-visible"):
            with self.subTest(selector=selector):
                self.assertIn(selector, css)

    def test_js_reads_endpoint_urls_from_dom(self):
        js = _read_static("sudoku/js/app.js")
        self.assertIn("dataset.validateUrl", js)
        self.assertIn("dataset.solveUrl", js)
        self.assertIn("fetch(", js)

    def test_js_handles_all_algorithm_identifiers(self):
        js = _read_static("sudoku/js/app.js")
        for identifier in ALGORITHM_IDENTIFIERS:
            with self.subTest(algorithm=identifier):
                self.assertIn(identifier, js)

    def test_js_builds_a_nine_by_nine_grid(self):
        js = _read_static("sudoku/js/app.js")
        # The build loop is 9x9 and targets the grid container.
        self.assertIn('getElementById("sudoku-grid")', js)
        self.assertIn("r < 9", js)
        self.assertIn("c < 9", js)
        self.assertIn('createElement("input")', js)

    def test_js_contains_the_example_puzzle(self):
        js = _read_static("sudoku/js/app.js")
        self.assertIn("[5, 3, 0, 0, 7, 0, 0, 0, 0]", js)

    def test_js_marks_stale_results_and_guards_requests(self):
        js = _read_static("sudoku/js/app.js")
        self.assertIn("markStale", js)
        self.assertIn("AbortController", js)

    def test_js_uses_relative_urls_not_hardcoded_host(self):
        js = _read_static("sudoku/js/app.js")
        self.assertNotIn("localhost", js)
        self.assertNotIn("127.0.0.1", js)


class ExamplePuzzleContractTests(SimpleTestCase):
    """The example puzzle satisfies the real API contract."""

    validate_url = reverse("sudoku:api_validate")
    solve_url = reverse("sudoku:api_solve")

    def test_example_puzzle_is_incomplete(self):
        empty = sum(row.count(0) for row in EXAMPLE_PUZZLE)
        self.assertGreater(empty, 0)

    def test_example_puzzle_validates(self):
        response = self.client.post(
            self.validate_url,
            data=json.dumps({"grid": EXAMPLE_PUZZLE}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["valid"])

    def test_every_algorithm_solves_the_example(self):
        for algorithm in ALGORITHM_IDENTIFIERS:
            with self.subTest(algorithm=algorithm):
                response = self.client.post(
                    self.solve_url,
                    data=json.dumps(
                        {"grid": EXAMPLE_PUZZLE, "algorithm": algorithm}
                    ),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 200)
                body = response.json()
                self.assertTrue(body["solved"])
                self.assertEqual(body["algorithm"], algorithm)
                self.assertEqual(body["solution"][0][0], 5)
