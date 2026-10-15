"""Shared realistic Sudoku fixtures for the test suite."""

# A known-complete, valid Sudoku solution (the classic "Wikipedia" solution).
VALID_SOLUTION = [
    [5, 3, 4, 6, 7, 8, 9, 1, 2],
    [6, 7, 2, 1, 9, 5, 3, 4, 8],
    [1, 9, 8, 3, 4, 2, 5, 6, 7],
    [8, 5, 9, 7, 6, 1, 4, 2, 3],
    [4, 2, 6, 8, 5, 3, 7, 9, 1],
    [7, 1, 3, 9, 2, 4, 8, 5, 6],
    [9, 6, 1, 5, 3, 7, 2, 8, 4],
    [2, 8, 7, 4, 1, 9, 6, 3, 5],
    [3, 4, 5, 2, 8, 6, 1, 7, 9],
]

# A classic puzzle derived from VALID_SOLUTION (0 = empty). Its clues are a
# subset of VALID_SOLUTION, so VALID_SOLUTION is its unique solution.
PUZZLE = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0],
    [6, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 8, 0, 0, 7, 9],
]

# An all-empty grid: structurally valid but with no clues.
EMPTY_GRID = [[0] * 9 for _ in range(9)]

# A structurally valid, clue-consistent but UNSOLVABLE puzzle. Cell (0, 0) has
# no legal candidate: its row supplies 1..8 and its column supplies 9, so no
# value from 1..9 can be placed. Tests assert these properties explicitly
# rather than assuming the puzzle is unsolvable.
UNSOLVABLE_NO_DUPLICATES = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8],
    [9, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
]


def swap_digits(grid, first: int, second: int):
    """Return a deep copy of ``grid`` with two digits swapped.

    Relabelling every occurrence of two digits maps a valid Sudoku grid to
    another valid grid, which is handy for building contrasting fixtures.
    """
    swapped = []
    for row in grid:
        swapped.append(
            [
                second if cell == first else first if cell == second else cell
                for cell in row
            ]
        )
    return swapped
