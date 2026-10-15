# Sudoku solver benchmark report

- **Generated:** 2026-10-15 16:55:42 UTC
- **Command:** `python -m sudoku.services.benchmark`
- **Repetitions per puzzle/algorithm:** 3
- **Algorithms:** `backtracking`, `mrv`, `mrv_forward_checking`
- **Puzzles benchmarked:** 6

## Dataset

Difficulty labels are **approximate**; see "Limitations".

| Identifier | Category (approx.) | Purpose |
|---|---|---|
| `already_completed` | already solved | Valid, complete grid with no empty cells; solvers must accept it immediately without assigning anything. |
| `easy_classic` | easy (approx.) | Clue-rich classic puzzle; the cheapest solvable case. Establishes a low-effort baseline for all three solvers. |
| `hard_inkala` | hard (approx.) | Sparse, high-effort puzzle (highest measured baseline search effort). Also exposes per-step heuristic overhead: the heuristics take far fewer search steps yet can spend more wall-clock time selecting cells. |
| `invalid_duplicate_clues` | invalid | Conflicting initial clues (duplicate 5 in row 1); must be classified as invalid input, never as unsolvable. |
| `medium_classic` | medium (approx.) | Moderately constrained puzzle where the baseline backtracker already needs a clearly larger search than the easy case. |
| `unsolvable_no_duplicates` | unsolvable | Well-formed and clue-consistent but provably unsolvable; must be classified as unsolvable, never as invalid input. |

## Methodology and metric definitions

- **Primary timing:** each solver's own `execution_time_ms`, measured with `time.perf_counter()` around the search only. Validation, Django, rendering and benchmark/report overhead are excluded.
- **Repeated runs:** `repetitions` runs per puzzle per algorithm; the report shows **median**, **minimum** and **maximum** of those measured times. Timings are reported exactly as measured (a `0.00` is a real measurement).
- **Search counters** (deterministic for a fixed puzzle and implementation, so all repetitions must agree):
  - `recursive_calls` -- entries into the recursive search, including the initial call.
  - `attempted_assignments` -- candidate values written into a cell for testing.
  - `backtracks` -- attempted assignments that failed and were undone.
- **Independent verification:** every `solved` result is re-checked with `is_valid_solution` before it is reported.
- **Classification:** `solved`, `unsolvable` (valid but no solution), `invalid_input` (malformed / conflicting clues) and `error` (unexpected solver exception). `invalid_input` is never reported as `unsolvable`, and `error` is never reported as either.
- **Fairness:** every algorithm receives its own independent copy of the same source puzzle; source puzzles are never modified.

## Outcome classification

| Identifier | Category | `backtracking` | `mrv` | `mrv_forward_checking` |
|---|---|---|---|---|
| `already_completed` | already solved | solved | solved | solved |
| `easy_classic` | easy (approx.) | solved | solved | solved |
| `hard_inkala` | hard (approx.) | solved | solved | solved |
| `invalid_duplicate_clues` | invalid | invalid_input | invalid_input | invalid_input |
| `medium_classic` | medium (approx.) | solved | solved | solved |
| `unsolvable_no_duplicates` | unsolvable | unsolvable | unsolvable | unsolvable |

## Detailed results

| Identifier | Algorithm | Status | Reps | Median ms | Min ms | Max ms | Calls | Assignments | Backtracks | Solution valid | Error |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `already_completed` | `backtracking` | solved | 3 | 0.0025 | 0.0024 | 0.0029 | 1 | 0 | 0 | true |  |
| `already_completed` | `mrv` | solved | 3 | 0.0029 | 0.0027 | 0.0037 | 1 | 0 | 0 | true |  |
| `already_completed` | `mrv_forward_checking` | solved | 3 | 0.0025 | 0.0024 | 0.0025 | 1 | 0 | 0 | true |  |
| `easy_classic` | `backtracking` | solved | 3 | 52.6 | 52.2 | 52.6 | 4209 | 4208 | 4157 | true |  |
| `easy_classic` | `mrv` | solved | 3 | 19.8 | 19.7 | 19.9 | 52 | 51 | 0 | true |  |
| `easy_classic` | `mrv_forward_checking` | solved | 3 | 38.5 | 38.4 | 38.7 | 52 | 51 | 0 | true |  |
| `hard_inkala` | `backtracking` | solved | 3 | 632 | 632 | 633 | 49559 | 49558 | 49498 | true |  |
| `hard_inkala` | `mrv` | solved | 3 | 5521 | 5509 | 5522 | 10102 | 10101 | 10041 | true |  |
| `hard_inkala` | `mrv_forward_checking` | solved | 3 | 10246 | 10246 | 10248 | 9180 | 10101 | 10041 | true |  |
| `invalid_duplicate_clues` | `backtracking` | invalid_input | 1 | -- | -- | -- | -- | -- | -- | -- | SudokuValidationError |
| `invalid_duplicate_clues` | `mrv` | invalid_input | 1 | -- | -- | -- | -- | -- | -- | -- | SudokuValidationError |
| `invalid_duplicate_clues` | `mrv_forward_checking` | invalid_input | 1 | -- | -- | -- | -- | -- | -- | -- | SudokuValidationError |
| `medium_classic` | `backtracking` | solved | 3 | 200 | 200 | 201 | 15495 | 15494 | 15437 | true |  |
| `medium_classic` | `mrv` | solved | 3 | 82.8 | 82.4 | 83.0 | 130 | 129 | 72 | true |  |
| `medium_classic` | `mrv_forward_checking` | solved | 3 | 151 | 151 | 152 | 121 | 129 | 72 | true |  |
| `unsolvable_no_duplicates` | `backtracking` | unsolvable | 3 | 0.0093 | 0.0092 | 0.0105 | 1 | 0 | 0 | -- |  |
| `unsolvable_no_duplicates` | `mrv` | unsolvable | 3 | 1.56 | 1.56 | 1.57 | 1 | 0 | 0 | -- |  |
| `unsolvable_no_duplicates` | `mrv_forward_checking` | unsolvable | 3 | 1.56 | 1.55 | 1.56 | 1 | 0 | 0 | -- |  |

## Comparison: puzzles solved by every algorithm

### `already_completed`

| Algorithm | Median ms | Min ms | Max ms | Recursive calls | Attempted assignments | Backtracks |
|---|---|---|---|---|---|---|
| `backtracking` | 0.0025 | 0.0024 | 0.0029 | 1 | 0 | 0 |
| `mrv` | 0.0029 | 0.0027 | 0.0037 | 1 | 0 | 0 |
| `mrv_forward_checking` | 0.0025 | 0.0024 | 0.0025 | 1 | 0 | 0 |

### `easy_classic`

| Algorithm | Median ms | Min ms | Max ms | Recursive calls | Attempted assignments | Backtracks |
|---|---|---|---|---|---|---|
| `backtracking` | 52.6 | 52.2 | 52.6 | 4,209 | 4,208 | 4,157 |
| `mrv` | 19.8 | 19.7 | 19.9 | 52 | 51 | 0 |
| `mrv_forward_checking` | 38.5 | 38.4 | 38.7 | 52 | 51 | 0 |

### `hard_inkala`

| Algorithm | Median ms | Min ms | Max ms | Recursive calls | Attempted assignments | Backtracks |
|---|---|---|---|---|---|---|
| `backtracking` | 632 | 632 | 633 | 49,559 | 49,558 | 49,498 |
| `mrv` | 5521 | 5509 | 5522 | 10,102 | 10,101 | 10,041 |
| `mrv_forward_checking` | 10246 | 10246 | 10248 | 9,180 | 10,101 | 10,041 |

### `medium_classic`

| Algorithm | Median ms | Min ms | Max ms | Recursive calls | Attempted assignments | Backtracks |
|---|---|---|---|---|---|---|
| `backtracking` | 200 | 200 | 201 | 15,495 | 15,494 | 15,437 |
| `mrv` | 82.8 | 82.4 | 83.0 | 130 | 129 | 72 |
| `mrv_forward_checking` | 151 | 151 | 152 | 121 | 129 | 72 |

## Observations

Lowest median wall-clock time on 4 commonly-solved puzzle(s): `backtracking` 2, `mrv` 2, `mrv_forward_checking` 0 (count = number of puzzles won).
Fewest recursive calls on the same puzzles: `backtracking` 1, `mrv` 1, `mrv_forward_checking` 2.
Fewer search steps did **not** always mean less wall-clock time (the heuristics pay per-step overhead for scanning cells and candidates):
- `hard_inkala`: fewest recursive calls came from `mrv_forward_checking` (9,180), yet `backtracking` was fastest in median wall-clock time (632 ms vs 10246 ms).
- `medium_classic`: fewest recursive calls came from `mrv_forward_checking` (121), yet `mrv` was fastest in median wall-clock time (82.8 ms vs 151 ms).

## What the charts show

- `execution_time.svg` -- median execution time (ms) per algorithm for the 4 puzzle(s) solved by **all** algorithms. Every bar is labelled with its actual value, so near-zero timings stay readable.
- `search_effort.svg` -- summed `recursive_calls`, `attempted_assignments` and `backtracks` per algorithm over the same puzzles; deterministic and therefore reproducible.
- Puzzles **excluded** from both charts: `invalid_duplicate_clues`, `unsolvable_no_duplicates` (invalid or unsolvable, or not solved by every algorithm).
- Raw data for every puzzle and algorithm is kept in `results.csv`.

## Limitations

- **Timings depend on hardware, system load and implementation details.** They are not intrinsic properties of an algorithm.
- **Timer resolution and system noise:** very short runs (fractions of a millisecond) can round to `0.00` or vary noticeably between repetitions.
- **Per-step heuristic overhead:** MRV/forward checking take far fewer search steps but pay for scanning cells and candidates on every step, so fewer calls do not guarantee a faster wall-clock time.
- **Small, hand-picked dataset:** no algorithm is claimed to be universally superior. The dataset exercises three difficulty tiers plus completed/unsolvable/invalid cases, not an exhaustive population.
- **Difficulty labels are approximate.** They were assigned by comparing the deterministic baseline backtracking search effort (recursive calls): easy 4,209; medium 15,495; hard 49,559. They are not authoritative human puzzle ratings.
- **Comparisons are only like-for-like:** the baseline's execution time is compared only against other solvers' execution times, never against a figure that includes benchmark or reporting overhead.
