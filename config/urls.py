"""
URL configuration for the AI-Based Sudoku Solver project.

All application routes live in the ``sudoku`` app and are included below:
the Phase 1 placeholder page plus the Phase 7 JSON API endpoints
(``/api/validate/`` and ``/api/solve/``). The frontend is added later.
"""

from django.urls import include, path

urlpatterns = [
    path("", include("sudoku.urls")),
]
