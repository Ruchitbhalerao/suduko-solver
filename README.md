# AI-Based Sudoku Solver

**Using Constraint Satisfaction Problems and Heuristic Search**

An academic mini project built with **Python** and **Django**, with a plain
**HTML / CSS / vanilla JavaScript** frontend. The AI engine lives in a
framework-independent Python package so it can be tested and reused on its own.

> **Current status: Phase 7 complete — JSON API + interactive frontend.**
> The AI package contains three solvers (backtracking, MRV, MRV + forward
> checking) and a standalone, Django-free benchmark service. Phase 7, part 1
> added JSON API endpoints for **validating** and **solving** puzzles; Phase 7,
> part 2 added the **interactive Sudoku interface**, built with plain HTML, CSS
> and vanilla JavaScript (no frontend framework or build step). Step-by-step
> solving visualization is **not** implemented yet.

---

## Progress checklist

- [x] **Phase 1** — Django project setup and placeholder page.
- [x] **Phase 2** — grid validation, constraint primitives, candidate generation.
- [x] **Phase 3** — basic recursive backtracking solver with metrics.
- [x] **Phase 4** — Minimum Remaining Values (MRV) heuristic search.
- [x] **Phase 5** — MRV + forward checking.
- [x] **Phase 6** — benchmarking and performance comparison.
- [x] **Phase 7, part 1** — HTTP API endpoints for validation and solving.
- [x] **Phase 7, part 2** — interactive frontend Sudoku interface.
- [ ] **Pending** — step-by-step solving visualization.

---

## Algorithms

| Algorithm | Status | Description |
|-----------|--------|-------------|
| Basic Backtracking | **Implemented** | Plain depth-first search with legality checks |
| Backtracking + MRV | **Implemented** | Heuristic: pick the cell with the **Minimum Remaining Values** |
| MRV + Forward Checking | **Implemented** | MRV plus pruning of impossible values from neighbors |

The engine uses only the Python standard library, so nothing extra must be
installed for the AI itself.

---

## Project structure

```
Suduko-solver/
├── config/                        # Django project package (settings + root URLs)
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py                # Minimal, DB-free Django settings
│   ├── urls.py                    # Root URL routing -> sudoku.urls
│   └── wsgi.py
├── sudoku/                        # Django application
│   ├── ai/                        # IMPORTANT: Django-free AI engine
│   │   ├── __init__.py
│   │   ├── backtracking.py        # Basic recursive backtracking solver
│   │   ├── constraints.py         # Legality checks, candidates, empty-cell search
│   │   ├── forward_checking.py    # MRV + forward checking search
│   │   ├── metrics.py             # SolverResult / SearchMetrics structures
│   │   ├── mrv.py                 # MRV heuristic search
│   │   └── solvers.py             # Algorithm registry (single source of truth)
│   ├── services/                  # IMPORTANT: Django-free benchmark services
│   │   ├── __init__.py
│   │   ├── benchmark.py           # Benchmark orchestration + CLI
│   │   └── reporting.py           # CSV / Markdown / SVG report writers
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── puzzles.py             # Phase 6 benchmark dataset
│   │   └── validation.py          # Grid structure, clues, and solution checks
│   ├── migrations/
│   ├── static/                    # IMPORTANT: static files (Django staticfiles)
│   │   └── sudoku/
│   │       ├── css/
│   │       │   └── styles.css     # Frontend layout, board, and cell states
│   │       └── js/
│   │           └── app.js         # Frontend grid behaviour + API calls
│   ├── templates/
│   │   └── sudoku/
│   │       └── placeholder.html   # Home page: interactive Sudoku interface
│   ├── tests/                     # Test package (run with `manage.py test`)
│   │   ├── __init__.py
│   │   ├── fixtures.py            # Shared realistic Sudoku grids
│   │   ├── test_phase1.py         # Placeholder-page tests
│   │   ├── test_constraints.py    # Constraint-primitive tests
│   │   ├── test_validation.py     # Validation and solution tests
│   │   ├── test_backtracking.py   # Backtracking-solver tests
│   │   ├── test_forward_checking.py  # MRV + forward checking tests
│   │   ├── test_mrv.py            # MRV-solver tests
│   │   ├── test_api.py            # HTTP API tests (Phase 7, part 1)
│   │   ├── test_frontend.py       # Frontend integration tests (Phase 7, part 2)
│   │   └── test_benchmark.py      # Benchmark service / report tests
│   ├── __init__.py
│   ├── api_views.py               # JSON API views: /api/validate/ and /api/solve/
│   ├── apps.py
│   ├── models.py                  # Empty (no database in this phase)
│   ├── urls.py                    # App URL routing (page + API endpoints)
│   └── views.py                   # Home-page view
├── benchmark_results/            # Generated benchmark artifacts (Phase 6)
│   ├── results.csv
│   ├── report.md
│   ├── execution_time.svg
│   └── search_effort.svg
├── .gitignore
├── check_env.py                   # Read-only environment verification script
├── manage.py
├── README.md
└── requirements.txt
```

The Django project package is named `config`; the application is named `sudoku`.

---

## Prerequisites

1. **Python 3.10 or newer.** (Developed and tested on Python 3.14 with Django 5.2 LTS.)
2. **pip** (comes with Python) and the `venv` module.
3. No Docker, cloud service, paid API, or internet access is required after
   dependencies are installed.

Check your Python version:

- **macOS / Ubuntu:** `python3 --version`
- **Windows PowerShell:** `py -3 --version`

If you see `command not found` or no version prints, install Python first from
<https://www.python.org/downloads/> (Windows: tick **"Add python.exe to PATH"**
during setup).

---

## Setup

The same three steps apply everywhere. Only the exact commands differ per
operating system.

1. Create and activate a **virtual environment**.
2. **Install** the dependencies into that environment.
3. **Run** Django's development server.

Never use `sudo pip install`. That modifies your system Python and can break
your machine. Everything is installed inside the project's own virtual
environment.

---

### macOS

```bash
# 1. From the project root, create the virtual environment
python3 -m venv .venv

# 2. Activate it (you should now see "(.venv)" at the start of your prompt)
source .venv/bin/activate

# 3. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# (Optional) verify the environment
python check_env.py

# 4. Run the development server
python manage.py runserver
```

Open <http://127.0.0.1:8000/> in your browser. You should see the Phase 1
placeholder page saying **"Django application is running."**

To stop the server, press `Ctrl + C` in the terminal. To leave the virtual
environment, run `deactivate`.

> **Apple Silicon note:** if `python3 -m venv .venv` fails, try
> `python3 -m venv --without-pip .venv` then re-run the pip install step, or
> reinstall Python from python.org so that `python3` and `pip3` are on your PATH.

---

### Windows PowerShell

```powershell
# 1. From the project root, create the virtual environment
py -3 -m venv .venv

# 2. Activate it
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# (Optional) verify the environment
python check_env.py

# 4. Run the development server
python manage.py runserver
```

Open <http://127.0.0.1:8000/> in your browser.

**If activation is blocked** with a message about scripts being disabled, run
this once in PowerShell (it only changes the policy for your user, not the
whole system), then retry activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Alternatively, skip activation entirely and call the environment's Python
directly:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

To stop the server, press `Ctrl + C`. To leave the virtual environment, run
`deactivate`.

---

### Ubuntu Linux (including college lab machines)

```bash
# 1. Install Python 3 and venv if they are missing
#    (Only needed if "python3 --version" fails. Requires internet/apt access.)
sudo apt update
sudo apt install -y python3 python3-venv python3-pip

# 2. From the project root, create the virtual environment
python3 -m venv .venv

# 3. Activate it
source .venv/bin/activate

# 4. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# (Optional) verify the environment
python check_env.py

# 5. Run the development server
python manage.py runserver
```

Open <http://127.0.0.1:8000/> in your browser.

> **Lab machines with read-only home directories:** if creating `.venv` fails
> with a permission error, place the project (or at least the virtual
> environment) somewhere you can write, for example:
> ```bash
> python3 -m venv /tmp/sudoku-venv
> source /tmp/sudoku-venv/activate
> ```

---

## Running the tests

With the virtual environment active, from the project root:

```bash
python manage.py test
```

The suite contains **218 tests**:

- **Phase 1** — the placeholder page is routed, returns **HTTP 200**, renders
  the correct template, and shows the project title.
- **Constraints** — legal/illegal placements (row, column, 3x3 box),
  zero-based indices, candidate generation, and empty-cell search.
- **Validation** — grid structure and cell types, duplicate clues, completeness,
  full solution verification (including clue preservation), and input-mutation
  safety.
- **Backtracking** — solving a known puzzle, rule/clue verification, input
  immutability, unsolvable and already-complete grids, malformed/duplicate
  rejection, performance counters, and Django-free operation.
- **MRV** — MRV cell selection (including minimum count and row/column tie-break),
  solving the same puzzles with far fewer recursive calls and backtracks,
  validation, immutability, unsolvable/already-complete cases, metrics, and
  Django-free operation.
- **Forward Checking** — the same solve/validation/immutability coverage plus
  focused probes that a domain wipeout is detected: a hand-built grid where a
  tentative assignment leaves a remaining cell with no candidates is rejected
  **before** any further recursion (verified by counters), and the shared MRV
  selector drives cell choice with deterministic tie-breaking.
- **API** — `POST /api/validate/` and `POST /api/solve/` at the HTTP level:
  valid/unsolvable/invalid classification, every supported algorithm, independent
  verification of returned solutions, clue preservation, all error and status
  codes (400/405/415/422/500), JSON content types, metric types, the existing
  page route, and that internal faults become a generic 500 rather than an
  "unsolvable" result.
- **Frontend** — the home page renders the Sudoku interface: grid container,
  all four control buttons, the algorithm selector with the three identifiers,
  status and results regions, correct references to both API endpoints, correct
  `{% static %}` references for the CSS/JS assets (confirmed to exist on disk),
  and the example puzzle that validates and is solved by all three algorithms
  through the real API. The JS is also checked for the algorithm identifiers,
  the grid loops, stale-result handling, and for having no hard-coded host.
- **Benchmark** — the service recognizes all three algorithm identifiers,
  gives each an equivalent independent copy, never mutates the source, verifies
  every solution, distinguishes `invalid_input` from `unsolvable` from `error`,
  rejects bad algorithm names and repetition counts, is deterministic in
  ordering and counters, and writes CSV/Markdown/SVG into a temporary directory.
  A subprocess test confirms the service is Django-free.

### Using the solver

```python
from sudoku.ai.backtracking import solve_backtracking
from sudoku.ai.forward_checking import solve_forward_checking
from sudoku.ai.mrv import solve_mrv

puzzle = [...]   # 9x9 list of lists (0 = empty)

result_bt = solve_backtracking(puzzle)
result_mrv = solve_mrv(puzzle)
result_fc = solve_forward_checking(puzzle)

if result_bt.solved:
    print("Backtracking solved:", result_bt.solution)
print(result_bt.recursive_calls, result_bt.attempted_assignments, result_bt.backtracks, result_bt.execution_time_ms)

if result_mrv.solved:
    print("MRV solved:", result_mrv.solution)
print(result_mrv.recursive_calls, result_mrv.attempted_assignments, result_mrv.backtracks, result_mrv.execution_time_ms)

if result_fc.solved:
    print("MRV + forward checking solved:", result_fc.solution)
print(result_fc.recursive_calls, result_fc.attempted_assignments, result_fc.backtracks, result_fc.execution_time_ms)
```

---

## Benchmarking (Phase 6)

Phase 6 compares the three solvers on a shared dataset and writes reproducible
reports. Benchmarking is kept **separate from the solvers**: the service only
drives the existing entry points and aggregates their real `SolverResult`
metrics, and it never imports Django.

### Architecture and locations

| Piece | Location |
|---|---|
| Benchmark dataset | `sudoku/utils/puzzles.py` |
| Benchmark service (`benchmark_puzzle`, `run_benchmarks`) | `sudoku/services/benchmark.py` |
| Report writers (CSV / Markdown / SVG) | `sudoku/services/reporting.py` |
| Tests | `sudoku/tests/test_benchmark.py` |
| Generated artifacts | `benchmark_results/` |

### Dataset

Every fixture is documented in `sudoku/utils/puzzles.py`. Difficulty labels are
**approximate** and are justified by the deterministic baseline search effort
(recursive calls), not by an authoritative rating.

| Identifier | Category (approx.) | Purpose |
|---|---|---|
| `easy_classic` | easy | Clue-rich classic puzzle; baseline needs ~4,209 calls. |
| `medium_classic` | medium | Moderately constrained; baseline needs ~15,495 calls. |
| `hard_inkala` | hard | Sparse Arto Inkala puzzle; baseline needs ~49,559 calls. |
| `already_completed` | already solved | Valid complete grid; accepted with no assignments. |
| `unsolvable_no_duplicates` | unsolvable | Clue-consistent but no solution. |
| `invalid_duplicate_clues` | invalid | Conflicting clues; rejected as invalid input. |

### Running the benchmark

From the project root, using the project virtual environment:

```bash
.venv/bin/python -m sudoku.services.benchmark
```

Optional flags: `--repetitions N` (default 3), `--algorithms NAME [NAME ...]`,
and `--output-dir PATH` (default `benchmark_results/`).

Output files:

- `benchmark_results/results.csv` — one row per (puzzle, algorithm); machine-readable.
- `benchmark_results/report.md` — dataset, methodology, tables, observations, limitations.
- `benchmark_results/execution_time.svg` — median execution time for puzzles solved by **all** algorithms.
- `benchmark_results/search_effort.svg` — summed recursive calls / assignments / backtracks.

### Metrics and timing rules

- **`repetitions`** — runs per puzzle per algorithm; the report shows the
  **median**, **minimum** and **maximum** of the measured times.
- **`execution_time_ms`** — each solver's own `time.perf_counter()` measurement
  around the search only. Validation, Django, rendering and benchmark overhead
  are excluded, so the baseline is never compared against an inflated figure.
- **`recursive_calls`** — entries to the recursive search, including the initial call.
- **`attempted_assignments`** — candidate values written into a cell for testing.
- **`backtracks`** — attempted assignments that failed and were undone.
- Counters are deterministic, so repetitions must agree; disagreement is reported
  (`counters_consistent = false`) instead of silently picking one value.
- **Statuses:** `solved`, `unsolvable`, `invalid_input`, `error`. Invalid input is
  never reported as unsolvable, and an unexpected exception is never reported as
  a normal result.
- Every successful solution is independently re-checked with `is_valid_solution`.

### How to read the tables and charts

- **Outcome classification** shows each puzzle/algorithm status.
- **Detailed results** lists median/min/max time plus the deterministic counters.
- **Comparison** tables (and the `execution_time.svg` chart) only include puzzles
  solved by *every* selected algorithm; invalid, unsolvable and partially-solved
  puzzles are listed as **excluded**. Every bar is labelled with its exact value,
  so near-zero timings stay readable.
- `search_effort.svg` sums the deterministic counters over the same puzzles.

### Limitations of timing comparisons

- Timings depend on **hardware, system load and implementation details**; they are
  not intrinsic properties of an algorithm.
- Very short runs (fractions of a millisecond) can round to `0.00` or vary
  between repetitions; such small differences are within timer noise.
- The heuristics take far fewer search steps but pay **per-step overhead** for
  scanning cells and candidates, so fewer calls do **not** always mean a faster
  wall-clock time.
- The dataset is small and hand-picked: **no algorithm is claimed to be
  universally superior**. Re-running the benchmark regenerates all artifacts.

---

## HTTP API (Phase 7, part 1)

Phase 7, part 1 exposes two synchronous JSON endpoints. They are a **thin HTTP
layer** over the existing AI engine: the views parse JSON, pick a solver from the
shared registry (`sudoku/ai/solvers.py`), and delegate all Sudoku logic to
`sudoku.utils.validation` and the solvers. No solver logic is re-implemented in
the views, and no database, background task, or external service is involved.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/validate/` | Check that a grid's structure and initial clues are valid. |
| `POST` | `/api/solve/` | Solve a grid with a chosen algorithm and return metrics. |

### Grid format

- A grid is a **9×9 JSON array of arrays**.
- `0` marks an **empty cell**; `1`–`9` are filled cells.
- Cells must be JSON integers (not floats, strings, or booleans).
- The caller's grid is never modified (the solvers copy it internally).

### Algorithm names

`algorithm` is optional and must be one of:

| Name | Implementation |
|---|---|
| `backtracking` | Basic recursive backtracking (the **default** when omitted) |
| `mrv` | Minimum Remaining Values heuristic |
| `mrv_forward_checking` | MRV + forward checking |

### `POST /api/validate/`

Checks structure and clues only. It **does not solve**, so a structurally valid
but unsolvable puzzle is reported as valid.

Request:

```json
{ "grid": [[5,3,0,0,7,0,0,0,0],[6,0,0,1,9,5,0,0,0],[0,9,8,0,0,0,0,6,0],
           [8,0,0,0,6,0,0,0,3],[4,0,0,8,0,3,0,0,1],[7,0,0,0,2,0,0,0,6],
           [0,6,0,0,0,0,2,8,0],[0,0,0,4,1,9,0,0,5],[0,0,0,0,8,0,0,7,9]] }
```

Valid response (`200`):

```json
{ "status": "valid", "valid": true, "message": "Grid structure and initial clues are valid." }
```

Invalid response (`422`):

```json
{ "status": "invalid_grid",
  "error": { "code": "invalid_grid", "message": "Duplicate clue value 5 in row 1." },
  "valid": false }
```

### `POST /api/solve/`

Request:

```json
{ "grid": [[5,3,0,0,7,0,0,0,0],[6,0,0,1,9,5,0,0,0],[0,9,8,0,0,0,0,6,0],
           [8,0,0,0,6,0,0,0,3],[4,0,0,8,0,3,0,0,1],[7,0,0,0,2,0,0,0,6],
           [0,6,0,0,0,0,2,8,0],[0,0,0,4,1,9,0,0,5],[0,0,0,0,8,0,0,7,9]],
  "algorithm": "mrv" }
```

Solved response (`200`):

```json
{ "status": "solved",
  "solved": true,
  "algorithm": "mrv",
  "solution": [[5,3,4,6,7,8,9,1,2],[6,7,2,1,9,5,3,4,8],[1,9,8,3,4,2,5,6,7],
               [8,5,9,7,6,1,4,2,3],[4,2,6,8,5,3,7,9,1],[7,1,3,9,2,4,8,5,6],
               [9,6,1,5,3,7,2,8,4],[2,8,7,4,1,9,6,3,5],[3,4,5,2,8,6,1,7,9]],
  "metrics": { "recursive_calls": 52, "attempted_assignments": 51,
               "backtracks": 0, "execution_time_ms": 22.36 },
  "message": "Puzzle solved with the mrv algorithm." }
```

Valid-but-unsolvable response (`200`):

```json
{ "status": "unsolvable", "solved": false, "algorithm": "backtracking",
  "solution": null,
  "metrics": { "recursive_calls": 1, "attempted_assignments": 0,
               "backtracks": 0, "execution_time_ms": 0.02 },
  "message": "The puzzle is valid but has no solution." }
```

`execution_time_ms` is the solver's own `perf_counter()` measurement around the
search only, exactly as reported by the normal `SolverResult`. It is machine
dependent and must not be compared for equality in tests.

### Invalid input vs a valid unsolvable puzzle

These are deliberately **different** outcomes:

- **Invalid input** — the grid is malformed or its clues conflict. The request is
  rejected with **422** and `"status": "invalid_grid"`.
- **Valid but unsolvable** — the grid is well-formed and clue-consistent but has
  no solution. This is a normal **200** response with `"status": "unsolvable"` and
  `"solved": false`.

Invalid input is never reported as unsolvable, and an unexpected internal failure
is never reported as either — it becomes a generic **500** (see below).

### HTTP status codes

| Code | Meaning | Used when |
|---|---|---|
| `200 OK` | Success | Valid grid; a solved puzzle; or a valid-but-unsolvable puzzle. |
| `400 Bad Request` | Client error | Malformed JSON, body not a JSON object, missing `grid`, `algorithm` not a string, or an unsupported algorithm. |
| `405 Method Not Allowed` | Wrong method | Any method other than `POST`. |
| `415 Unsupported Media Type` | Wrong content type | `Content-Type` is not `application/json`. |
| `422 Unprocessable Entity` | Semantically invalid grid | Grid fails structural or clue validation. |
| `500 Internal Server Error` | Server fault | An unexpected/internal solver failure. Logged server-side; the response is generic. |

Error responses share a stable shape:

```json
{ "status": "<code>", "error": { "code": "<code>", "message": "<human-readable>" } }
```

plus `"valid": false` (validation) or `"solved": false` (solving) where relevant.
Raw Python tracebacks and internal exception details are never returned. The
framework-generated **405** response is the one exception to the JSON body: it has
an empty `text/html` body.

Both endpoints require a JSON body and accept only `POST`. They are
`csrf_exempt` because this is a **stateless JSON API** with no sessions, cookies,
or authentication, so there is no CSRF-protected state; this is also what allows
plain `curl` calls to work.

### Testing the API locally with `curl`

Start the server, then call the endpoints:

```bash
python manage.py runserver 127.0.0.1:8000
```

```bash
# 1. Validate a valid puzzle
curl -s -X POST http://127.0.0.1:8000/api/validate/ \
  -H "Content-Type: application/json" \
  -d '{"grid": [[5,3,0,0,7,0,0,0,0],[6,0,0,1,9,5,0,0,0],[0,9,8,0,0,0,0,6,0],[8,0,0,0,6,0,0,0,3],[4,0,0,8,0,3,0,0,1],[7,0,0,0,2,0,0,0,6],[0,6,0,0,0,0,2,8,0],[0,0,0,4,1,9,0,0,5],[0,0,0,0,8,0,0,7,9]]}'

# 2. Solve it with MRV
curl -s -X POST http://127.0.0.1:8000/api/solve/ \
  -H "Content-Type: application/json" \
  -d '{"grid": [[5,3,0,0,7,0,0,0,0],[6,0,0,1,9,5,0,0,0],[0,9,8,0,0,0,0,6,0],[8,0,0,0,6,0,0,0,3],[4,0,0,8,0,3,0,0,1],[7,0,0,0,2,0,0,0,6],[0,6,0,0,0,0,2,8,0],[0,0,0,4,1,9,0,0,5],[0,0,0,0,8,0,0,7,9]], "algorithm": "mrv"}'
```

Verified with the running development server: `POST /api/validate/` returned
`200`, `POST /api/solve/` with `mrv` returned `200`, a duplicate-clue grid
returned `422`, an unsolvable-but-valid grid returned `200`
(`"status": "unsolvable"`), an unsupported algorithm returned `400`, malformed
JSON returned `400`, a non-JSON content type returned `415`, and `GET` returned
`405`.

---

## Frontend (Phase 7, part 2)

The home page (`sudoku/templates/sudoku/placeholder.html`) is now an interactive
Sudoku interface built with **plain HTML, CSS and vanilla JavaScript** — no
React, no Vue, no build step, no extra dependency. The responsibilities are
split the usual way:

| Piece | Location | Responsibility |
|---|---|---|
| Page structure | `sudoku/templates/sudoku/placeholder.html` | Markup, labels, panels, endpoint URLs |
| Styles | `sudoku/static/sudoku/css/styles.css` | Layout, responsiveness, cell states, focus |
| Behaviour | `sudoku/static/sudoku/js/app.js` | Grid editing, API calls, rendering results |

> The template and view keep their historical Phase 1 names
> (`placeholder.html` / `views.placeholder`) so the original route and tests
> continue to work; only their content changed.

### Start the server and open the interface

```bash
# from the project root, with the virtual environment active
.venv/bin/python manage.py runserver
```

Then open **<http://127.0.0.1:8000/>**. The same server serves both the page and
the JSON API, so no separate configuration is needed. Static assets
(`/static/sudoku/...`) are served automatically while `DEBUG = True`.

### Using the grid

- The board is **81 editable cells** laid out as nine 3×3 boxes.
- Type digits **1–9**; leave a cell blank for an empty square. The frontend sends
  empty cells as **`0`**, matching the API contract.
- Non-digit input is filtered out, so pasted or stray characters are handled
  safely instead of corrupting the grid.
- **Arrow keys** move between cells (wrapping at the edges), so the grid is fully
  usable from the keyboard.
- Cell colours are meaningful: **original clues** are shaded and bold, values you
  typed are blue, and cells **filled by the solver** are green.

### Buttons

| Button | What it does |
|---|---|
| **Load example** | Fills the grid with a deterministic, known valid, incomplete puzzle that the validation endpoint accepts. |
| **Validate** | `POST`s the grid to `/api/validate/` and shows the returned status/message. |
| **Solve** | `POST`s the grid and the selected algorithm to `/api/solve/` and renders the result. |
| **Clear grid** | Empties the grid and resets the results. |

### Choosing an algorithm

The **Solver algorithm** selector offers exactly the three identifiers the API
accepts:

- `backtracking` — Backtracking (baseline)
- `mrv` — MRV (Minimum Remaining Values)
- `mrv_forward_checking` — MRV + Forward Checking

### Reading the solver metrics

After a solve, the results panel shows the values the API actually returned:

- **Status** — `Solved` or `Unsolvable`.
- **Algorithm** — which solver ran.
- **Recursive calls** — entries to the recursive search.
- **Attempted assignments** — candidate values written into a cell for testing.
- **Backtracks** — attempted assignments that failed and were undone.
- **Execution time** — the solver's own measurement, in milliseconds.

Only API-returned values are ever displayed; nothing is estimated. Fewer search
steps do **not** automatically mean less wall-clock time (the heuristics pay
per-step overhead), so compare the numbers rather than assuming one algorithm is
always fastest. Before any successful solve, the panel shows an empty state.

### Stale results

The frontend keeps a copy of the puzzle it submitted. If you **edit the grid or
change the algorithm after a solve**, the previous result stays visible but is
clearly marked with a note that it no longer describes the current puzzle, and
in-flight responses are cancelled/ignored so a late reply can never overwrite
newer edits.

### If an API request fails

- **Invalid grid** (`422`) and **unsupported algorithm** (`400`) show the API's
  own error message.
- **Malformed/unexpected responses** and **server errors** (`5xx`) show a short,
  plain-language message instead of a stack trace.
- **Network failure** (server not running) shows *"Could not reach the server…"*.
- Buttons are disabled while a request is in flight (with `Solving…` /
  `Validating…` labels) and are restored when it finishes.

### Manual browser testing checklist

Browser automation is **not available** in this environment (neither Selenium nor
Playwright is installed, and adding such a dependency is out of scope for a few
checks). The automated suite therefore covers the page, its markup, static assets
and API contract; the interactive behaviour should be checked by hand:

1. `runserver`, open <http://127.0.0.1:8000/> — page loads, no console errors.
2. You see a 9×9 board inside nine 3×3 boxes, four buttons and an algorithm list.
3. Press **Load example** — cells fill; given numbers look different from blanks.
4. Type `5` in an empty cell, then type `0` and a letter — only `1`–`9` survive.
5. Use **arrow keys** to move around the board; focus ring is clearly visible.
6. Click **Validate** — status shows the API's "valid" message.
7. Choose **backtracking**, click **Solve** — grid fills, original clues keep
   their style, new cells appear in a different colour, and metrics are shown.
8. Repeat step 7 for **mrv** and **mrv_forward_checking**.
9. Load the example, change the algorithm after solving — the stale-results note
   appears and old metrics are flagged.
10. Enter a valid-but-unsolvable puzzle and press **Solve** — the message says it
    has no solution and the grid is not shown as solved.
11. Stop the server and press **Solve** — the network-error message appears and
    the buttons recover.
12. Resize the window narrow — the layout stacks and the board stays usable.

### Still pending

Step-by-step solving visualization, search-process animation, and the benchmark
dashboard remain **pending** and are not part of this step.

---

## Django commands you will use

```bash
python manage.py check     # sanity-check the project without starting a server
python manage.py test      # run the automated test suite
python manage.py runserver # start the development server
```

**About migrations:** this phase has no database models, so you do **not** need
to run migrations yet. When models are added in a later phase, run:

```bash
python manage.py makemigrations
python manage.py migrate
```

---

## Environment verification script

`check_env.py` performs a **read-only** check of your interpreter. It reports:

- whether Python is 3.10 or newer,
- whether a virtual environment is active,
- whether Django is importable and which version is installed.

```bash
python check_env.py
```

It prints `PASS`/`FAIL` for each item and exits with code `0` on success, `1` on
failure. It never installs or changes anything.

---

## Troubleshooting

| Problem | Likely cause and fix |
|---------|----------------------|
| `python: command not found` (macOS/Linux) | Your shell only knows `python3`. Use `python3` (or `python3 -m venv ...`) instead of `python`, or use the virtual environment's `python` after activation. |
| `python3: command not found` | Python is not installed. Install Python 3.10+ from <https://www.python.org/downloads/>. |
| `'py' is not recognized` (Windows) | Use the full installer from python.org (tick "Add python.exe to PATH") so the `py` launcher is available. |
| `Permission denied` or `externally-managed-environment` | You are installing into a system Python. Activate `.venv` first, and never use `sudo pip install`. |
| `Error: [Errno 48] Address already in use` | Port 8000 is occupied (a previous server is still running). Press `Ctrl + C` in that terminal, or run on a different port: `python manage.py runserver 8080`. |
| `.venv/Scripts/Activate.ps1` disabled (Windows) | PowerShell script execution is restricted. Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, or call `.\.venv\Scripts\python.exe manage.py runserver` directly. |
| `ModuleNotFoundError: No module named 'django'` | Dependencies are not installed in the active interpreter. Re-activate `.venv` and run `python -m pip install -r requirements.txt`. |
| `django.db.utils...` or a `db.sqlite3` error | Not expected in Phase 1. If it appears, confirm you are on the project root and that no stray `DATABASES` override exists in `config/settings.py`. |

---

## License

For academic use as part of coursework.
