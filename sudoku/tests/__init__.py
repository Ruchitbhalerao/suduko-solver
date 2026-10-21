"""Automated tests for the sudoku application.

Test modules:
    * ``test_phase1``      -- the Django placeholder-page tests.
    * ``test_constraints`` -- the AI constraint primitives.
    * ``test_validation``  -- grid validation and solution checking.

The AI-engine tests use ``SimpleTestCase`` (no database) and import the
framework-independent ``sudoku.ai`` / ``sudoku.utils`` modules directly.
"""
