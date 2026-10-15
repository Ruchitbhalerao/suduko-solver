"""Phase 1 tests: the Django placeholder page is wired up and reachable.

These are the four original Phase 1 tests, unchanged, moved into the
``sudoku.tests`` package. Because no database is used, they extend
``SimpleTestCase``.
"""

from django.test import SimpleTestCase
from django.urls import reverse


class PlaceholderPageTests(SimpleTestCase):
    """Checks that the Phase 1 placeholder page responds correctly."""

    def test_placeholder_url_resolves(self):
        self.assertEqual(reverse("sudoku:placeholder"), "/")

    def test_placeholder_returns_http_200(self):
        response = self.client.get(reverse("sudoku:placeholder"))
        self.assertEqual(response.status_code, 200)

    def test_placeholder_shows_project_title(self):
        response = self.client.get(reverse("sudoku:placeholder"))
        self.assertContains(response, "AI-Based Sudoku Solver")

    def test_placeholder_uses_expected_template(self):
        response = self.client.get(reverse("sudoku:placeholder"))
        self.assertTemplateUsed(response, "sudoku/placeholder.html")
