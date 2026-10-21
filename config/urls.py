"""
URL configuration for the AI-Based Sudoku Solver project.

All application routes live in the ``sudoku`` app and are included below:
the interactive frontend page plus the Phase 7 JSON API endpoints
(``/api/validate/``, ``/api/solve/``, ``/api/generate/``, and image extraction).
"""

from django.urls import include, path

urlpatterns = [
    path("", include("sudoku.urls")),
]
