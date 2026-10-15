from django.urls import path

from . import api_views, views

app_name = "sudoku"

urlpatterns = [
    path("", views.placeholder, name="placeholder"),
    path("api/validate/", api_views.api_validate, name="api_validate"),
    path("api/solve/", api_views.api_solve, name="api_solve"),
    path("api/extract-sudoku/", api_views.api_extract_sudoku, name="api_extract_sudoku"),
]
