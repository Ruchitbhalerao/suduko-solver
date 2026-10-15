"""Report and chart generation for the Sudoku benchmark service (Phase 6).

Writes the three artifacts produced by Phase 6 from a :class:`BenchmarkSuite`:

* ``results.csv``      -- one row per (puzzle, algorithm), machine-readable.
* ``report.md``        -- readable comparison tables, findings and limitations.
* ``execution_time.svg`` / ``search_effort.svg`` -- comparison charts.

Only the Python standard library is used to build the SVGs (hand-written
generator), so no plotting dependency is required. This module never imports
Django, and it never invents data: every number rendered comes straight from
the solver-reported metrics passed in the suite.

Only puzzles that were **solved by all selected algorithms** enter the charts;
invalid and unsolvable cases are reported as classifications in the CSV and
Markdown instead, and are explicitly listed as excluded.
"""

from __future__ import annotations

import csv
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

from sudoku.services.benchmark import (
    STATUS_SOLVED,
    AlgorithmOutcome,
    BenchmarkSuite,
    PuzzleBenchmark,
)

__all__ = [
    "RESULTS_CSV",
    "REPORT_MD",
    "EXECUTION_TIME_SVG",
    "SEARCH_EFFORT_SVG",
    "write_reports",
]

RESULTS_CSV = "results.csv"
REPORT_MD = "report.md"
EXECUTION_TIME_SVG = "execution_time.svg"
SEARCH_EFFORT_SVG = "search_effort.svg"

CSV_COLUMNS = [
    "puzzle_id",
    "category",
    "algorithm",
    "status",
    "repetitions",
    "median_time_ms",
    "min_time_ms",
    "max_time_ms",
    "recursive_calls",
    "attempted_assignments",
    "backtracks",
    "counters_consistent",
    "solution_valid",
    "error_type",
    "error_message",
]

_COLOR_PALETTE = ("#1f6feb", "#d9730d", "#2da44e", "#8250df", "#cf222e", "#0588f0")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fmt_ms(value: float) -> str:
    """Human-readable milliseconds without inventing precision."""
    if value == 0:
        return "0.00"
    if value >= 100:
        return f"{value:.0f}"
    if value >= 10:
        return f"{value:.1f}"
    if value >= 1:
        return f"{value:.2f}"
    text = f"{value:.4f}".rstrip("0")
    return text + "0" if text.endswith(".") else text


def _fmt_count(value: float) -> str:
    """Human-readable integer counters."""
    return f"{value:,.0f}"


def _cell(value) -> str:
    """Format an optional value for CSV output (``None`` -> empty)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)
    return str(value)


def _common_solved(
    suite: BenchmarkSuite,
) -> List[Tuple[str, List[AlgorithmOutcome]]]:
    """Return ``(identifier, outcomes)`` for puzzles solved by every algorithm."""
    common = []
    for puzzle in suite.results:
        outcomes = list(puzzle.outcomes)
        if len(outcomes) != len(suite.algorithms):
            continue
        if all(outcome.status == STATUS_SOLVED for outcome in outcomes):
            common.append((puzzle.identifier, outcomes))
    common.sort(key=lambda item: item[0])
    return common


def _excluded_puzzles(suite: BenchmarkSuite) -> List[str]:
    """Identifiers of puzzles left out of the successful-solution charts."""
    solved_ids = {identifier for identifier, _ in _common_solved(suite)}
    return [
        puzzle.identifier for puzzle in suite.results if puzzle.identifier not in solved_ids
    ]


def _status_by_algorithm(puzzle: PuzzleBenchmark) -> Dict[str, str]:
    return {outcome.algorithm: outcome.status for outcome in puzzle.outcomes}


# ---------------------------------------------------------------------------
# SVG chart generation (standard library only)
# ---------------------------------------------------------------------------

def _bar_chart_svg(
    *,
    title: str,
    subtitle: str,
    x_label: str,
    y_label: str,
    categories: Sequence[str],
    series: Sequence[Tuple[str, Sequence[float]]],
    format_value: Callable[[float], str],
    footnote: Sequence[str],
    width: int = 960,
    height: int = 620,
    value_suffix: str = "",
) -> str:
    """Render a grouped bar chart as SVG markup.

    ``series`` is a sequence of ``(name, values)`` where ``values`` align with
    ``categories``. A title, axis labels, legend, per-bar numeric values and a
    footnote are always included so the chart stays interpretable even when the
    bars themselves are tiny or zero-height.
    """
    esc = html.escape
    parts: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Helvetica, Arial, sans-serif">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{width / 2}" y="30" text-anchor="middle" font-size="18" '
        f'font-weight="bold" fill="#111111">{esc(title)}</text>',
        f'<text x="{width / 2}" y="52" text-anchor="middle" font-size="11" '
        f'fill="#555555">{esc(subtitle)}</text>',
    ]

    left, right, top, bottom = 95, 30, 100, 210
    plot_w = width - left - right
    plot_h = height - top - bottom
    plot_bottom = top + plot_h
    x_tick_y = plot_bottom + 22
    x_title_y = plot_bottom + 95
    footnote_y0 = plot_bottom + 122
    value_label_offset = 5

    if not categories or not series:
        parts.append(
            f'<text x="{width / 2}" y="{height / 2}" text-anchor="middle" '
            f'font-size="15" fill="#333333">No comparable successful-solution '
            f'data for this chart.</text>'
        )
        no_data_y0 = height - 40 - (len(footnote) - 1) * 16
        for index, line in enumerate(footnote):
            parts.append(
                f'<text x="{left}" y="{no_data_y0 + index * 16}" font-size="11" '
                f'fill="#444444">{esc(line)}</text>'
            )
        parts.append("</svg>")
        return "".join(parts)

    raw_max = max(max(values) for _, values in series)
    scale_max = raw_max * 1.15 if raw_max > 0 else 1.0
    if raw_max == 0:
        parts.append(
            f'<text x="{left}" y="{top - 8}" font-size="11" fill="#b35c00">'
            f"All measured values are exactly 0 (below timer resolution); bars "
            f"are drawn at zero height and the numeric labels show the values."
            f"</text>"
        )

    def y_of(value: float) -> float:
        return top + plot_h - (value / scale_max) * plot_h

    # Y axis ticks and grid lines.
    tick_count = 5
    for tick in range(tick_count + 1):
        value = scale_max * tick / tick_count
        y = y_of(value)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" '
            f'stroke="#e4e4e4" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="11" '
            f'fill="#444444">{esc(format_value(value))}</text>'
        )

    # Axes.
    parts.append(
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" '
        f'stroke="#333333" stroke-width="1.5"/>'
    )
    parts.append(
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" '
        f'y2="{top + plot_h}" stroke="#333333" stroke-width="1.5"/>'
    )

    # Axis titles.
    parts.append(
        f'<text x="24" y="{top + plot_h / 2}" text-anchor="middle" font-size="13" '
        f'fill="#222222" transform="rotate(-90 24 {top + plot_h / 2})">{esc(y_label)}</text>'
    )
    parts.append(
        f'<text x="{left + plot_w / 2}" y="{x_title_y}" '
        f'text-anchor="middle" font-size="13" fill="#222222">{esc(x_label)}</text>'
    )

    n_series = len(series)
    group_w = plot_w / len(categories)
    bar_area = group_w * 0.72
    bar_w = bar_area / n_series

    for cat_index, category in enumerate(categories):
        group_x = left + cat_index * group_w + (group_w - bar_area) / 2
        # X tick label (rotated for long identifiers).
        label_x = group_x + bar_area / 2
        label_y = x_tick_y
        parts.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" font-size="11" fill="#333333" '
            f'text-anchor="end" transform="rotate(-30 {label_x:.1f} {label_y:.1f})">'
            f"{esc(category)}</text>"
        )
        for series_index, (name, values) in enumerate(series):
            value = values[cat_index]
            x = group_x + series_index * bar_w
            y = y_of(value)
            bar_h = max(plot_bottom - y, 0.0)
            color = _COLOR_PALETTE[series_index % len(_COLOR_PALETTE)]
            # Guarantee a visible sliver for a genuine zero measurement.
            draw_h = bar_h if bar_h > 0 else 1.5
            parts.append(
                f'<rect x="{x:.2f}" y="{(y if bar_h > 0 else plot_bottom - 1.5):.2f}" '
                f'width="{bar_w - 2:.2f}" height="{draw_h:.2f}" fill="{color}" '
                f'rx="2"/>'
            )
            parts.append(
                f'<text x="{x + (bar_w - 2) / 2:.2f}" y="{y - value_label_offset:.1f}" '
                f'text-anchor="middle" font-size="9" fill="#222222">'
                f"{esc(format_value(value) + value_suffix)}</text>"
            )

    # Legend (top, under the subtitle).
    legend_x = left
    legend_y = 78
    for series_index, (name, _) in enumerate(series):
        color = _COLOR_PALETTE[series_index % len(_COLOR_PALETTE)]
        parts.append(
            f'<rect x="{legend_x}" y="{legend_y - 10}" width="13" height="13" '
            f'fill="{color}" rx="2"/>'
        )
        parts.append(
            f'<text x="{legend_x + 19}" y="{legend_y}" font-size="12" '
            f'fill="#222222">{esc(name)}</text>'
        )
        legend_x += 26 + len(name) * 7

    # Footnote block.
    for index, line in enumerate(footnote):
        parts.append(
            f'<text x="{left}" y="{footnote_y0 + index * 16}" font-size="10.5" '
            f'fill="#444444">{esc(line)}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


def render_execution_time_svg(suite: BenchmarkSuite) -> str:
    """SVG comparing median solver time (ms) on commonly-solved puzzles."""
    common = _common_solved(suite)
    excluded = _excluded_puzzles(suite)
    categories = [identifier for identifier, _ in common]
    series = [
        (
            algorithm,
            [
                next(o.median_time_ms for o in outcomes if o.algorithm == algorithm)
                for _, outcomes in common
            ],
        )
        for algorithm in suite.algorithms
        if common
    ]

    footnote = [
        f"Values: median solver execution time (ms) over {suite.repetitions} "
        "repetition(s); measured inside each solver by time.perf_counter().",
        "Machine- and load-dependent: these timings are NOT a property of the "
        "algorithm alone. Validation, Django, rendering and report overhead are "
        "excluded. A value of 0.00 is a real measurement, never an illustration.",
        "Linear scale: one slow puzzle can visually compress the smaller bars; "
        "the exact value is printed above every bar.",
        "Included (solved by all selected algorithms): "
        + (", ".join(categories) if categories else "(none)"),
        "Excluded from this chart (invalid / unsolvable / not solved by all): "
        + (", ".join(excluded) if excluded else "(none)"),
    ]

    return _bar_chart_svg(
        title="Median solver execution time by algorithm",
        subtitle=(
            f"Repetitions: {suite.repetitions}  |  algorithms: "
            f"{', '.join(suite.algorithms)}"
        ),
        x_label="Benchmark puzzle identifier",
        y_label="Median execution time (ms)",
        categories=categories,
        series=series,
        format_value=_fmt_ms,
        footnote=footnote,
        value_suffix="",
    )


def render_search_effort_svg(suite: BenchmarkSuite) -> str:
    """SVG comparing search effort (summed over commonly-solved puzzles)."""
    common = _common_solved(suite)
    excluded = _excluded_puzzles(suite)
    metrics = [
        ("Recursive calls", lambda o: o.recursive_calls),
        ("Attempted assignments", lambda o: o.attempted_assignments),
        ("Backtracks", lambda o: o.backtracks),
    ]

    series = []
    for algorithm in suite.algorithms:
        totals = []
        for _, getter in metrics:
            total = 0
            for _, outcomes in common:
                outcome = next(o for o in outcomes if o.algorithm == algorithm)
                value = getter(outcome)
                total += value or 0
            totals.append(float(total))
        if common:
            series.append((algorithm, totals))

    included = ", ".join(identifier for identifier, _ in common) or "(none)"
    footnote = [
        f"Values: sum of each search counter across the {len(common)} puzzle(s) "
        "solved by all selected algorithms. Counters are deterministic, so they "
        "are reproducible (unlike timings).",
        "recursive_calls = entries to the recursive search (incl. the initial "
        "call); attempted_assignments = candidate values written for testing; "
        "backtracks = assignments undone.",
        f"Included: {included}",
        "Excluded from this chart (invalid / unsolvable / not solved by all): "
        + (", ".join(excluded) if excluded else "(none)"),
    ]

    return _bar_chart_svg(
        title="Search effort by algorithm (summed counters)",
        subtitle=(
            f"Aggregated over {len(common)} commonly-solved puzzle(s)  |  "
            f"algorithms: {', '.join(suite.algorithms)}"
        ),
        x_label="Search counter",
        y_label="Count (summed over included puzzles)",
        categories=[name for name, _ in metrics],
        series=series,
        format_value=_fmt_count,
        footnote=footnote,
    )


# ---------------------------------------------------------------------------
# File writers
# ---------------------------------------------------------------------------

def write_csv(suite: BenchmarkSuite, path: Path) -> Path:
    """Write the machine-readable results table."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        for puzzle in suite.results:
            for outcome in puzzle.outcomes:
                writer.writerow(
                    [
                        puzzle.identifier,
                        puzzle.category,
                        outcome.algorithm,
                        outcome.status,
                        outcome.repetitions,
                        _cell(outcome.median_time_ms),
                        _cell(outcome.min_time_ms),
                        _cell(outcome.max_time_ms),
                        _cell(outcome.recursive_calls),
                        _cell(outcome.attempted_assignments),
                        _cell(outcome.backtracks),
                        _cell(outcome.counters_consistent),
                        _cell(outcome.solution_valid),
                        _cell(outcome.error_type),
                        _cell(outcome.error_message),
                    ]
                )
    return path


def _observations(suite: BenchmarkSuite) -> List[str]:
    """Compute factual observations directly from the measured results."""
    common = _common_solved(suite)
    lines: List[str] = []

    if not common:
        lines.append(
            "No puzzle was solved by every selected algorithm, so no "
            "like-for-like comparison is available."
        )
        return lines

    time_wins: Dict[str, int] = {name: 0 for name in suite.algorithms}
    effort_wins: Dict[str, int] = {name: 0 for name in suite.algorithms}
    divergences: List[str] = []
    noisy_divergence = False

    for identifier, outcomes in common:
        by_time = min(outcomes, key=lambda o: o.median_time_ms)
        by_effort = min(outcomes, key=lambda o: o.recursive_calls)
        time_wins[by_time.algorithm] += 1
        effort_wins[by_effort.algorithm] += 1
        if by_time.algorithm != by_effort.algorithm:
            if (
                by_time.median_time_ms < 0.1
                and by_effort.median_time_ms < 0.1
            ):
                noisy_divergence = True
            divergences.append(
                f"`{identifier}`: fewest recursive calls came from "
                f"`{by_effort.algorithm}` ({by_effort.recursive_calls:,}), yet "
                f"`{by_time.algorithm}` was fastest in median wall-clock time "
                f"({_fmt_ms(by_time.median_time_ms)} ms vs "
                f"{_fmt_ms(by_effort.median_time_ms)} ms)."
            )

    lines.append(
        "Lowest median wall-clock time on " + str(len(common)) + " commonly-solved "
        "puzzle(s): "
        + ", ".join(f"`{name}` {count}" for name, count in time_wins.items())
        + " (count = number of puzzles won)."
    )
    lines.append(
        "Fewest recursive calls on the same puzzles: "
        + ", ".join(f"`{name}` {count}" for name, count in effort_wins.items())
        + "."
    )

    if divergences:
        lines.append(
            "Fewer search steps did **not** always mean less wall-clock time "
            "(the heuristics pay per-step overhead for scanning cells and "
            "candidates):"
        )
        lines.extend(f"- {line}" for line in divergences)
        if noisy_divergence:
            lines.append(
                "- Note: divergences where both medians are below 0.1 ms fall "
                "within timer resolution and system noise, and should not be "
                "over-interpreted."
            )
    else:
        lines.append(
            "For these puzzles the algorithm with the fewest recursive calls was "
            "also the fastest in median wall-clock time."
        )
    return lines


def render_markdown(suite: BenchmarkSuite) -> str:
    """Render the human-readable Markdown report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    common = _common_solved(suite)
    excluded = _excluded_puzzles(suite)
    algorithms = list(suite.algorithms)

    lines: List[str] = []
    lines.append("# Sudoku solver benchmark report")
    lines.append("")
    lines.append(f"- **Generated:** {now}")
    lines.append("- **Command:** `python -m sudoku.services.benchmark`")
    lines.append(f"- **Repetitions per puzzle/algorithm:** {suite.repetitions}")
    lines.append(f"- **Algorithms:** {', '.join(f'`{a}`' for a in algorithms)}")
    lines.append(f"- **Puzzles benchmarked:** {len(suite.results)}")
    lines.append("")

    lines.append("## Dataset")
    lines.append("")
    lines.append("Difficulty labels are **approximate**; see \"Limitations\".")
    lines.append("")
    lines.append("| Identifier | Category (approx.) | Purpose |")
    lines.append("|---|---|---|")
    for puzzle in suite.results:
        lines.append(
            f"| `{puzzle.identifier}` | {puzzle.category} | {puzzle.purpose} |"
        )
    lines.append("")

    lines.append("## Methodology and metric definitions")
    lines.append("")
    lines.append(
        "- **Primary timing:** each solver's own `execution_time_ms`, measured "
        "with `time.perf_counter()` around the search only. Validation, Django, "
        "rendering and benchmark/report overhead are excluded."
    )
    lines.append(
        "- **Repeated runs:** `repetitions` runs per puzzle per algorithm; the "
        "report shows **median**, **minimum** and **maximum** of those measured "
        "times. Timings are reported exactly as measured (a `0.00` is a real "
        "measurement)."
    )
    lines.append(
        "- **Search counters** (deterministic for a fixed puzzle and "
        "implementation, so all repetitions must agree):"
    )
    lines.append(
        "  - `recursive_calls` -- entries into the recursive search, including "
        "the initial call."
    )
    lines.append(
        "  - `attempted_assignments` -- candidate values written into a cell for "
        "testing."
    )
    lines.append(
        "  - `backtracks` -- attempted assignments that failed and were undone."
    )
    lines.append(
        "- **Independent verification:** every `solved` result is re-checked with "
        "`is_valid_solution` before it is reported."
    )
    lines.append(
        "- **Classification:** `solved`, `unsolvable` (valid but no solution), "
        "`invalid_input` (malformed / conflicting clues) and `error` (unexpected "
        "solver exception). `invalid_input` is never reported as `unsolvable`, "
        "and `error` is never reported as either."
    )
    lines.append(
        "- **Fairness:** every algorithm receives its own independent copy of the "
        "same source puzzle; source puzzles are never modified."
    )
    lines.append("")

    lines.append("## Outcome classification")
    lines.append("")
    header = "| Identifier | Category | " + " | ".join(f"`{a}`" for a in algorithms) + " |"
    lines.append(header)
    lines.append("|---|---|" + "---|" * len(algorithms))
    for puzzle in suite.results:
        statuses = _status_by_algorithm(puzzle)
        lines.append(
            f"| `{puzzle.identifier}` | {puzzle.category} | "
            + " | ".join(statuses[a] for a in algorithms)
            + " |"
        )
    lines.append("")

    lines.append("## Detailed results")
    lines.append("")
    lines.append(
        "| Identifier | Algorithm | Status | Reps | Median ms | Min ms | Max ms | "
        "Calls | Assignments | Backtracks | Solution valid | Error |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for puzzle in suite.results:
        for outcome in puzzle.outcomes:
            lines.append(
                f"| `{puzzle.identifier}` | `{outcome.algorithm}` | "
                f"{outcome.status} | {outcome.repetitions} | "
                f"{_fmt_ms(outcome.median_time_ms) if outcome.median_time_ms is not None else '--'} | "
                f"{_fmt_ms(outcome.min_time_ms) if outcome.min_time_ms is not None else '--'} | "
                f"{_fmt_ms(outcome.max_time_ms) if outcome.max_time_ms is not None else '--'} | "
                f"{outcome.recursive_calls if outcome.recursive_calls is not None else '--'} | "
                f"{outcome.attempted_assignments if outcome.attempted_assignments is not None else '--'} | "
                f"{outcome.backtracks if outcome.backtracks is not None else '--'} | "
                f"{'--' if outcome.solution_valid is None else str(outcome.solution_valid).lower()} | "
                f"{outcome.error_type or ''} |"
            )
    lines.append("")

    lines.append("## Comparison: puzzles solved by every algorithm")
    lines.append("")
    if not common:
        lines.append("_No puzzle was solved by every selected algorithm._")
        lines.append("")
    for identifier, outcomes in common:
        lines.append(f"### `{identifier}`")
        lines.append("")
        lines.append(
            "| Algorithm | Median ms | Min ms | Max ms | Recursive calls | "
            "Attempted assignments | Backtracks |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for outcome in outcomes:
            lines.append(
                f"| `{outcome.algorithm}` | {_fmt_ms(outcome.median_time_ms)} | "
                f"{_fmt_ms(outcome.min_time_ms)} | {_fmt_ms(outcome.max_time_ms)} | "
                f"{outcome.recursive_calls:,} | "
                f"{outcome.attempted_assignments:,} | {outcome.backtracks:,} |"
            )
        lines.append("")

    lines.append("## Observations")
    lines.append("")
    lines.extend(_observations(suite))
    lines.append("")

    lines.append("## What the charts show")
    lines.append("")
    lines.append(
        f"- `{EXECUTION_TIME_SVG}` -- median execution time (ms) per algorithm for "
        f"the {len(common)} puzzle(s) solved by **all** algorithms. Every bar is "
        "labelled with its actual value, so near-zero timings stay readable."
    )
    lines.append(
        f"- `{SEARCH_EFFORT_SVG}` -- summed `recursive_calls`, "
        f"`attempted_assignments` and `backtracks` per algorithm over the same "
        "puzzles; deterministic and therefore reproducible."
    )
    if excluded:
        lines.append(
            "- Puzzles **excluded** from both charts: "
            + ", ".join(f"`{i}`" for i in excluded)
            + " (invalid or unsolvable, or not solved by every algorithm)."
        )
    lines.append(
        f"- Raw data for every puzzle and algorithm is kept in `{RESULTS_CSV}`."
    )
    lines.append("")

    lines.append("## Limitations")
    lines.append("")
    lines.append(
        "- **Timings depend on hardware, system load and implementation details.** "
        "They are not intrinsic properties of an algorithm."
    )
    lines.append(
        "- **Timer resolution and system noise:** very short runs (fractions of a "
        "millisecond) can round to `0.00` or vary noticeably between repetitions."
    )
    lines.append(
        "- **Per-step heuristic overhead:** MRV/forward checking take far fewer "
        "search steps but pay for scanning cells and candidates on every step, so "
        "fewer calls do not guarantee a faster wall-clock time."
    )
    lines.append(
        "- **Small, hand-picked dataset:** no algorithm is claimed to be "
        "universally superior. The dataset exercises three difficulty tiers plus "
        "completed/unsolvable/invalid cases, not an exhaustive population."
    )
    lines.append(
        "- **Difficulty labels are approximate.** They were assigned by comparing "
        "the deterministic baseline backtracking search effort (recursive calls): "
        "easy 4,209; medium 15,495; hard 49,559. They are not authoritative "
        "human puzzle ratings."
    )
    lines.append(
        "- **Comparisons are only like-for-like:** the baseline's execution time "
        "is compared only against other solvers' execution times, never against a "
        "figure that includes benchmark or reporting overhead."
    )
    lines.append("")
    return "\n".join(lines)


def write_markdown(suite: BenchmarkSuite, path: Path) -> Path:
    """Write the Markdown report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(suite), encoding="utf-8")
    return path


def write_svg(suite: BenchmarkSuite, path: Path, renderer) -> Path:
    """Write an SVG produced by ``renderer(suite)``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(renderer(suite), encoding="utf-8")
    return path


def write_reports(suite: BenchmarkSuite, output_dir: Path) -> Dict[str, Path]:
    """Write all four artifacts into ``output_dir`` and return their paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "csv": write_csv(suite, output_dir / RESULTS_CSV),
        "markdown": write_markdown(suite, output_dir / REPORT_MD),
        "execution_time_svg": write_svg(
            suite, output_dir / EXECUTION_TIME_SVG, render_execution_time_svg
        ),
        "search_effort_svg": write_svg(
            suite, output_dir / SEARCH_EFFORT_SVG, render_search_effort_svg
        ),
    }
    return paths
