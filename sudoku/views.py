"""Views for the sudoku application.

Phase 1 contains only a placeholder view. It proves that the Django project is
correctly configured and serving requests. No Sudoku logic lives here: the AI
engine is kept completely independent of Django.
"""

import platform

import django
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def placeholder(request: HttpRequest) -> HttpResponse:
    """Render the Phase 1 placeholder page.

    Reports the running Python and Django versions so that the page doubles as
    a quick environment sanity check.
    """
    context = {
        "python_version": platform.python_version(),
        "django_version": django.get_version(),
    }
    return render(request, "sudoku/placeholder.html", context)
