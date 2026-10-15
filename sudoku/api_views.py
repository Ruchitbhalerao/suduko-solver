"""JSON API views for validating and solving Sudoku puzzles (Phase 7, part 1).

These views are a *thin* HTTP layer. Every piece of Sudoku logic -- grid
validation, candidate generation, and the three search algorithms -- is
delegated to the framework-independent AI engine (``sudoku.utils.validation``
and ``sudoku.ai``). Nothing is re-implemented here: the views only parse JSON,
pick a solver from the shared registry, and translate the result into HTTP
status codes and JSON bodies.

Design choices (documented in the README and asserted by ``test_api.py``)
-------------------------------------------------------------------------
* Only ``POST`` is accepted; other methods get **405 Method Not Allowed**.
* A JSON request body is required. A different content type gets
  **415 Unsupported Media Type**, and unparseable JSON gets **400 Bad Request**.
* A well-formed request whose *grid* fails Sudoku validation (bad dimensions,
  non-integer or out-of-range cells, duplicate clues) gets
  **422 Unprocessable Entity**. This keeps invalid input clearly distinct from a
  valid-but-unsolvable puzzle (which is a normal **200** answer).
* An unsupported algorithm name is a request error and gets **400**.
* ``algorithm`` is optional; when omitted, :data:`DEFAULT_ALGORITHM` is used.
* An unexpected internal failure is logged and reported as a generic
  **500 Internal Server Error**; raw tracebacks and exception details are never
  returned, and such a failure is never mislabelled as "unsolvable".
* CSRF protection is disabled for these endpoints: this is a stateless JSON API
  with no sessions, cookies, or authentication, so there is nothing for CSRF to
  protect. This also lets plain ``curl`` calls work.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from sudoku.ai.backtracking import SolverError
from sudoku.ai.metrics import SolverResult
from sudoku.ai.solvers import ALGORITHM_RUNNERS, ALGORITHMS, DEFAULT_ALGORITHM
from sudoku.utils.validation import SudokuValidationError, validate_grid

logger = logging.getLogger(__name__)

# HTTP status codes used by the API (kept explicit and named for readability).
HTTP_200_OK = 200
HTTP_400_BAD_REQUEST = 400
HTTP_415_UNSUPPORTED_MEDIA_TYPE = 415
HTTP_422_UNPROCESSABLE_ENTITY = 422
HTTP_500_INTERNAL_SERVER_ERROR = 500

JSON_MEDIA_TYPE = "application/json"

# Stable machine-readable error codes returned to clients.
CODE_MALFORMED_JSON = "malformed_json"
CODE_INVALID_REQUEST = "invalid_request"
CODE_UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
CODE_INVALID_GRID = "invalid_grid"
CODE_UNSUPPORTED_ALGORITHM = "unsupported_algorithm"
CODE_INTERNAL_ERROR = "internal_error"


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    extra: Optional[Dict[str, Any]] = None,
) -> JsonResponse:
    """Build a consistent JSON error response.

    The body always carries a top-level ``error`` object with a stable ``code``
    and a human-readable ``message``. ``extra`` lets each endpoint add the flags
    that make sense for it (``valid`` for validation, ``solved``/``algorithm``
    for solving) without duplicating this structure.
    """
    body: Dict[str, Any] = {
        "status": code,
        "error": {"code": code, "message": message},
    }
    if extra:
        body.update(extra)
    return JsonResponse(body, status=status_code)


def _parse_json_body(request: HttpRequest) -> Tuple[Optional[Dict[str, Any]], Optional[JsonResponse]]:
    """Parse a required JSON object body.

    Returns ``(data, None)`` on success or ``(None, error_response)`` on failure.
    """
    media_type = (request.content_type or "").split(";")[0].strip().lower()
    if media_type != JSON_MEDIA_TYPE:
        return None, _error_response(
            status_code=HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            code=CODE_UNSUPPORTED_MEDIA_TYPE,
            message="Request body must be JSON (Content-Type: application/json).",
        )

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, _error_response(
            status_code=HTTP_400_BAD_REQUEST,
            code=CODE_MALFORMED_JSON,
            message="Request body must be valid JSON.",
        )

    if not isinstance(data, dict):
        return None, _error_response(
            status_code=HTTP_400_BAD_REQUEST,
            code=CODE_INVALID_REQUEST,
            message="Request body must be a JSON object.",
        )

    return data, None


def _extract_grid(data: Dict[str, Any]) -> Tuple[Optional[Any], Optional[JsonResponse]]:
    """Return the raw ``grid`` field, or a 400 error response when it is absent.

    The value is intentionally *not* type-checked here: the shared validation
    module is the single authority on what a well-formed grid is, and its
    failure is reported as 422 further down.
    """
    if "grid" not in data:
        return None, _error_response(
            status_code=HTTP_400_BAD_REQUEST,
            code=CODE_INVALID_REQUEST,
            message="Missing required field 'grid'.",
        )
    return data["grid"], None


def _extract_algorithm(data: Dict[str, Any]) -> Tuple[Optional[str], Optional[JsonResponse]]:
    """Return a validated algorithm name, or a 400 error response.

    Omitting ``algorithm`` selects :data:`DEFAULT_ALGORITHM`. A non-string value
    or an unknown name is a request error.
    """
    if "algorithm" not in data:
        return DEFAULT_ALGORITHM, None

    algorithm = data["algorithm"]
    if not isinstance(algorithm, str):
        return None, _error_response(
            status_code=HTTP_400_BAD_REQUEST,
            code=CODE_INVALID_REQUEST,
            message="Field 'algorithm' must be a string.",
        )

    if algorithm not in ALGORITHM_RUNNERS:
        supported = ", ".join(ALGORITHMS)
        return None, _error_response(
            status_code=HTTP_400_BAD_REQUEST,
            code=CODE_UNSUPPORTED_ALGORITHM,
            message=(
                f"Unsupported algorithm {algorithm!r}. "
                f"Supported algorithms are: {supported}."
            ),
        )

    return algorithm, None


def _metrics_payload(result: SolverResult) -> Dict[str, Any]:
    """Serialize the search metrics for a solver result."""
    return {
        "recursive_calls": int(result.recursive_calls),
        "attempted_assignments": int(result.attempted_assignments),
        "backtracks": int(result.backtracks),
        "execution_time_ms": float(result.execution_time_ms),
    }


def _invalid_grid_response(
    exc: SudokuValidationError, *, valid: bool = False, algorithm: Optional[str] = None
) -> JsonResponse:
    """422 response for a grid that fails structural/clue validation."""
    extra: Dict[str, Any] = {"valid": valid}
    if algorithm is not None:
        extra["solved"] = False
        extra["algorithm"] = algorithm
    return _error_response(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        code=CODE_INVALID_GRID,
        message=str(exc),
        extra=extra,
    )


@csrf_exempt
@require_POST
def api_validate(request: HttpRequest) -> JsonResponse:
    """``POST /api/validate/`` -- report whether a grid is well-formed.

    The grid's structure and initial clues are checked; the puzzle is *not*
    solved. A structurally valid but unsolvable puzzle is therefore reported as
    valid.
    """
    data, error = _parse_json_body(request)
    if error is not None:
        return error

    grid, error = _extract_grid(data)  # type: ignore[arg-type]
    if error is not None:
        return error

    try:
        validate_grid(grid)
    except SudokuValidationError as exc:
        return _invalid_grid_response(exc, valid=False)

    return JsonResponse(
        {
            "status": "valid",
            "valid": True,
            "message": "Grid structure and initial clues are valid.",
        },
        status=HTTP_200_OK,
    )


@csrf_exempt
@require_POST
def api_solve(request: HttpRequest) -> JsonResponse:
    """``POST /api/solve/`` -- solve a grid with a chosen algorithm.

    The returned solution is produced by the existing solver, which independently
    verifies it before reporting success. Invalid input (422) and a valid but
    unsolvable puzzle (200 with ``status: unsolvable``) are reported distinctly.
    """
    data, error = _parse_json_body(request)
    if error is not None:
        return error

    grid, error = _extract_grid(data)  # type: ignore[arg-type]
    if error is not None:
        return error

    algorithm, error = _extract_algorithm(data)  # type: ignore[arg-type]
    if error is not None:
        return error

    # Look the runner up at call time so the registry stays the single source of
    # truth and can be substituted in tests without touching the solvers.
    runner = ALGORITHM_RUNNERS[algorithm]  # type: ignore[index]

    try:
        result = runner(grid)
    except SudokuValidationError as exc:
        return _invalid_grid_response(exc, valid=False, algorithm=algorithm)
    except SolverError:
        # The solver produced a grid that failed its own verification. That is an
        # internal fault, not a client error and definitely not "unsolvable".
        logger.exception("Solver %r failed internal verification.", algorithm)
        return _error_response(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            code=CODE_INTERNAL_ERROR,
            message="The solver encountered an internal error.",
            extra={"solved": False, "algorithm": algorithm},
        )
    except Exception:  # noqa: BLE001 - never leak tracebacks or mislabel as unsolvable
        logger.exception("Unexpected error while solving with %r.", algorithm)
        return _error_response(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            code=CODE_INTERNAL_ERROR,
            message="The solver encountered an internal error.",
            extra={"solved": False, "algorithm": algorithm},
        )

    if not isinstance(result, SolverResult):
        logger.error(
            "Solver %r returned %s, expected SolverResult.",
            algorithm,
            type(result).__name__,
        )
        return _error_response(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            code=CODE_INTERNAL_ERROR,
            message="The solver encountered an internal error.",
            extra={"solved": False, "algorithm": algorithm},
        )

    metrics = _metrics_payload(result)

    if result.solved:
        return JsonResponse(
            {
                "status": "solved",
                "solved": True,
                "algorithm": algorithm,
                "solution": result.solution,
                "metrics": metrics,
                "message": f"Puzzle solved with the {algorithm} algorithm.",
            },
            status=HTTP_200_OK,
        )

    return JsonResponse(
        {
            "status": "unsolvable",
            "solved": False,
            "algorithm": algorithm,
            "solution": None,
            "metrics": metrics,
            "message": "The puzzle is valid but has no solution.",
        },
        status=HTTP_200_OK,
    )
