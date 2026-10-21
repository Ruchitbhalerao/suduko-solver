"""Digit classification for extracted Sudoku cells.

Approach
--------
A small k-nearest-neighbours classifier trained *locally*, at import time, on
synthetic digits rendered with OpenCV's Hershey fonts at several sizes,
thicknesses, offsets and -- crucially for photographed boards -- slight
rotation angles, with light morphological and noise augmentation.  Only NumPy
is needed for the classifier itself (OpenCV 5 no longer ships the ``cv2.ml``
module), so there is no model file to download, no paid service and no large
runtime dependency.

Three independent gates decide what ends up in the grid:

1. *Geometry* -- a cell is blank unless it holds a blob of roughly digit
   proportions; long thin blobs hugging a cell border are grid-line
   fragments and are discarded before anything else runs.
2. *Agreement* -- the ``k`` nearest neighbours must agree, and that fraction
   is reported as the confidence.
3. *Consistency* -- a kept digit's distance to the training manifold and its
   size must be in line with the other digits found *on the same board*.
   Absolute thresholds cannot do this: a heavily re-photographed glyph is
   legitimately farther from every rendered template than a clean one, so
   only relative comparisons separate real digits from remnants.

Anything rejected while still holding ink is reported as *uncertain* rather
than guessed, so the caller can show it for review instead of silently
inventing a clue.
"""

from __future__ import annotations

<<<<<<< HEAD
import os
=======
>>>>>>> 8489722e6d638ec6bfd2c5806e03208df452060e
import threading
from dataclasses import dataclass, field

import cv2
import numpy as np

CANVAS = 28
CROP = 20  # digit fitted into a 20x20 box centred on a 28x28 canvas
FEATURES = CANVAS * CANVAS
<<<<<<< HEAD
# Classification uses a *distance-weighted* vote among the nearest templates:
# each of the K nearest votes for its digit with weight 1/distance, so a clearly
# closest template carries the decision even when the raw neighbour counts are
# split.  A plain majority vote discards the right answer on printed boards --
# the correct digit is often the single nearest template, but the next few
# nearest belong to look-alike digits and outvote it, so the cell is dropped.
K = 9
WEIGHTED_ACCEPT = 0.55  # the winning digit must hold this share of the vote
MIN_SCORE = 0.8  # kept for reference; superseded by WEIGHTED_ACCEPT
=======
K = 5
MIN_SCORE = 0.8  # below this a cell is reported as unknown
>>>>>>> 8489722e6d638ec6bfd2c5806e03208df452060e
# A kept digit may be at most this many times farther from the training
# manifold than the typical digit on the same board (with an absolute floor so
# a board of near-perfect matches does not over-tighten the rule).
RELATIVE_DISTANCE_FACTOR = 2.5
RELATIVE_DISTANCE_FLOOR = 60.0

_FONTS = (
    cv2.FONT_HERSHEY_SIMPLEX,
    cv2.FONT_HERSHEY_PLAIN,
    cv2.FONT_HERSHEY_DUPLEX,
    cv2.FONT_HERSHEY_COMPLEX,
    cv2.FONT_HERSHEY_TRIPLEX,
    cv2.FONT_HERSHEY_COMPLEX_SMALL,
)

# Photographed boards are rarely perfectly upright; without these the
# classifier misreads tilted digits (a tilted 9 becomes a 7, a tilted 1 with
# a serif becomes a 2), which is exactly how duplicated clues appeared.
_ROTATIONS = (-10, -5, 5, 10)

_lock = threading.Lock()
_samples: np.ndarray | None = None
_labels: np.ndarray | None = None


@dataclass
class CellReading:
    """What one cell patch contains after every gate has run."""

    digit: int = 0
    confidence: float = 0.0
    has_ink: bool = False
    ink_height: int = 0  # bounding-box height of the largest blob (0 if none)
    distance: float = float("inf")  # distance to the nearest training glyph
    reasons: list[str] = field(default_factory=list)


def _components(img: np.ndarray) -> tuple[int, np.ndarray, np.ndarray]:
    binary = (img > 127).astype(np.uint8)
    return cv2.connectedComponentsWithStats(binary, connectivity=8)[:3]


def _largest_blobs(img: np.ndarray) -> np.ndarray | None:
    """Keep the digit-shaped components and discard specks."""
    binary = (img > 127).astype(np.uint8)
    num, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if num <= 1:
        return None
    areas = stats[1:, cv2.CC_STAT_AREA]
    biggest = float(areas.max())
    keep = np.zeros_like(img, dtype=np.uint8)
    for index, area in enumerate(areas, start=1):
        if area >= max(8.0, biggest * 0.15):
            keep[labels == index] = 255
    return keep if keep.any() else None


def normalise_digit(img: np.ndarray) -> np.ndarray | None:
    """Turn a white-on-black patch into a flat length-``FEATURES`` vector."""
    if img is None or getattr(img, "size", 0) == 0:
        return None
    binary = np.asarray(img, dtype=np.uint8)
    binary = (binary > 127).astype(np.uint8) * 255
    binary = _largest_blobs(binary)
    if binary is None:
        return None

    ys, xs = np.nonzero(binary)
    if ys.size == 0:
        return None
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    crop = binary[y0:y1, x0:x1]
    h, w = crop.shape
    if h == 0 or w == 0:
        return None

    scale = CROP / float(max(h, w))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    resized = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_AREA)
    resized = (resized > 127).astype(np.uint8) * 255

    canvas = np.zeros((CANVAS, CANVAS), dtype=np.uint8)
    pad_y = (CANVAS - new_h) // 2
    pad_x = (CANVAS - new_w) // 2
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized

    # Centre of mass: removes small position shifts between fonts and boards.
    moments = cv2.moments(canvas, binaryImage=True)
    if moments["m00"] > 0:
        dx = int(round(CANVAS / 2 - moments["m10"] / moments["m00"]))
        dy = int(round(CANVAS / 2 - moments["m01"] / moments["m00"]))
        shift = np.float32([[1, 0, dx], [0, 1, dy]])
        canvas = cv2.warpAffine(canvas, shift, (CANVAS, CANVAS))

    return (canvas.astype(np.float32) / 255.0).reshape(-1)


def _render(digit: int, font: int, scale: float, thickness: int,
            shift: int, rotation: int, rng: np.random.Generator) -> np.ndarray | None:
    img = np.zeros((48, 48), dtype=np.uint8)
    text = str(digit)
    for _ in range(5):
        (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
        if tw + 10 <= 48 and th + 10 <= 48:
            break
        scale *= 0.85
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    x = int((48 - tw) // 2 + rng.integers(-shift, shift + 1))
    y = int((48 + th - baseline) // 2 + rng.integers(-shift, shift + 1))
    cv2.putText(img, text, (x, y), font, scale, 255, thickness, cv2.LINE_AA)

    if rotation:
        matrix = cv2.getRotationMatrix2D((24.0, 24.0), float(rotation), 1.0)
        img = cv2.warpAffine(
            img, matrix, (48, 48), flags=cv2.INTER_LINEAR, borderValue=0
        )

    variant = int(rng.integers(0, 4))
    if variant == 1:
        img = cv2.erode(img, np.ones((2, 2), np.uint8))
    elif variant == 2:
        img = cv2.dilate(img, np.ones((2, 2), np.uint8))

    # Photographs of boards are low-resolution compared to a freshly rendered
    # glyph: a cell may hold a 14-pixel digit.  Shrinking and growing the
    # template back up puts the same soft, chunked strokes into the training
    # set, which is the main domain gap between renders and real captures.
    if rng.random() < 0.6:
        factor = float(rng.uniform(0.3, 0.7))
        small = cv2.resize(
            img, (max(1, int(48 * factor)),) * 2, interpolation=cv2.INTER_AREA
        )
        img = cv2.resize(small, (48, 48), interpolation=cv2.INTER_LINEAR)
    if rng.random() < 0.4:
        kernel = 3 if rng.random() < 0.5 else 5
        img = cv2.GaussianBlur(img, (kernel, kernel), 0)

    vector = normalise_digit(img)
    if vector is None:
        return None
    if rng.random() < 0.5:
        vector = np.clip(vector + rng.normal(0.0, 0.03, vector.shape), 0.0, 1.0)
    return vector.astype(np.float32)


def _training_set() -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(20261015)
    samples: list[np.ndarray] = []
    labels: list[int] = []
    for digit in range(1, 10):
        for font in _FONTS:
            for scale in (1.6, 2.0, 2.5):
                for thickness in (1, 2, 3):
                    for rotation in (0, *_ROTATIONS):
                        vec = _render(digit, font, scale, thickness, 3, rotation, rng)
                        if vec is not None:
                            samples.append(vec)
                            labels.append(digit)
    return np.vstack(samples), np.asarray(labels, dtype=np.int32)


<<<<<<< HEAD
_TEMPLATE_BANK = os.path.join(os.path.dirname(__file__), "digit_templates.npz")


def _load_template_bank() -> tuple[np.ndarray, np.ndarray] | None:
    """Load the baked digit-template bank shipped with the package.

    The bank (Hershey renders + digits from common TrueType fonts) is built
    offline by ``tools/build_digit_templates.py`` and stored quantised to
    ``uint8``; it is what lets the classifier read real printed boards.  Returns
    ``None`` if the file is missing so the caller can fall back to generating
    the Hershey-only set at import time.
    """
    if not os.path.exists(_TEMPLATE_BANK):
        return None
    try:
        with np.load(_TEMPLATE_BANK) as data:
            samples = data["samples"].astype(np.float32) / 255.0
            labels = data["labels"].astype(np.int32)
    except Exception:
        return None
    if samples.ndim != 2 or samples.shape[1] != FEATURES or samples.shape[0] != labels.shape[0]:
        return None
    return np.ascontiguousarray(samples, dtype=np.float32), labels


=======
>>>>>>> 8489722e6d638ec6bfd2c5806e03208df452060e
def _ensure_model() -> None:
    global _samples, _labels
    if _samples is None:
        with _lock:
            if _samples is None:
<<<<<<< HEAD
                bank = _load_template_bank()
                if bank is not None:
                    _samples, _labels = bank
                else:
                    samples, labels = _training_set()
                    _samples = np.ascontiguousarray(samples, dtype=np.float32)
                    _labels = labels
=======
                samples, labels = _training_set()
                _samples = np.ascontiguousarray(samples, dtype=np.float32)
                _labels = labels
>>>>>>> 8489722e6d638ec6bfd2c5806e03208df452060e


# ---------------------------------------------------------------------------
# Cell geometry gates
# ---------------------------------------------------------------------------


def _looks_like_line_fragment(stats: np.ndarray, cell_h: int, cell_w: int) -> bool:
    """True for a long thin blob hugging a border: a leftover grid line.

    Digits are compact (their bounding box is never a 3px-wide stripe across
    the whole cell), so this can be decided purely on geometry.
    """
    x, y, w, h, area = int(stats[0]), int(stats[1]), int(stats[2]), int(stats[3]), int(stats[4])
    if area < 8:
        return False
    thin_vertical = h >= 0.6 * cell_h and w <= max(3, 0.12 * cell_w)
    thin_horizontal = w >= 0.6 * cell_w and h <= max(3, 0.12 * cell_h)
    if not (thin_vertical or thin_horizontal):
        return False
    touches = x <= 1 or y <= 1 or (x + w) >= cell_w - 1 or (y + h) >= cell_h - 1
    return touches


def clean_cell(cell: np.ndarray) -> np.ndarray | None:
    """Drop specks and border-hugging line fragments; ``None`` when nothing left.

    Returns a 0/255 uint8 patch, or ``None`` if the cell holds no usable ink.
    """
    if cell is None or getattr(cell, "size", 0) == 0:
        return None
    binary = (np.asarray(cell, dtype=np.uint8) > 127).astype(np.uint8)
    if not binary.any():
        return None
    height, width = binary.shape[:2]
    num, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if num <= 1:
        return None

    minimum_area = max(5, int(0.004 * height * width))
    keep = np.zeros_like(binary)
    kept_any = False
    for index in range(1, num):
        stat = stats[index]
        if stat[cv2.CC_STAT_AREA] < minimum_area:
            continue
        if _looks_like_line_fragment(stat, height, width):
            continue
        keep[labels == index] = 1
        kept_any = True
    if not kept_any:
        return None
    return keep * 255


def is_probably_empty(cell: np.ndarray) -> bool:
    """True when a cell patch holds no usable digit ink.

    ``cell`` must already have been through :func:`clean_cell` for best
    results; the thresholds are relative to the cell area so they hold for
    any segmentation size.
    """
    if cell is None or getattr(cell, "size", 0) == 0:
        return True
    binary = (np.asarray(cell) > 127).astype(np.uint8)
    total = int(binary.size)
    if total == 0:
        return True
<<<<<<< HEAD
    if int(binary.sum()) < max(8.0, total * 0.008):
=======
    if int(binary.sum()) < max(10.0, total * 0.012):
>>>>>>> 8489722e6d638ec6bfd2c5806e03208df452060e
        return True
    num, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if num <= 1:
        return True
    areas = stats[1:, cv2.CC_STAT_AREA]
    biggest = int(areas.max())
<<<<<<< HEAD
    # Emptiness is decided on the *shape* of the largest blob, not on how much
    # ink it holds: a printed board photographed at modest resolution draws its
    # digits with thin strokes, so a real 1 or 7 covers barely 2% of its cell.
    # An area-fraction gate tuned for bold glyphs silently drops those, which is
    # how most clues went missing.  A low absolute floor only rejects specks.
    if biggest < max(12.0, total * 0.010):
=======
    if biggest < max(15.0, total * 0.035):
>>>>>>> 8489722e6d638ec6bfd2c5806e03208df452060e
        return True
    index = 1 + int(np.argmax(areas))
    height, width = binary.shape[:2]
    box_h = int(stats[index][cv2.CC_STAT_HEIGHT])
    box_w = int(stats[index][cv2.CC_STAT_WIDTH])
<<<<<<< HEAD
    # A digit spans a good part of its cell's height; specks and smudges do not,
    # no matter how many of them there are.  Width is allowed to be small so
    # thin glyphs (1) are not mistaken for emptiness.
    if box_h < 0.22 * height:
        return True
    if box_w < 0.07 * width:
=======
    # A digit occupies a substantial part of its cell; specks and smudges do
    # not, no matter how many of them there are.
    if box_h < 0.26 * height:
        return True
    if box_w < 0.10 * width:
>>>>>>> 8489722e6d638ec6bfd2c5806e03208df452060e
        return True
    return False


def _largest_blob_height(cell: np.ndarray) -> int:
    binary = (np.asarray(cell) > 127).astype(np.uint8)
    num, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if num <= 1:
        return 0
    return int(stats[1:, cv2.CC_STAT_HEIGHT].max())


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def read_cell(cell: np.ndarray) -> CellReading:
    """Run every gate on one cell patch and report what it contains."""
    cleaned = clean_cell(cell)
    if cleaned is None:
        return CellReading(digit=0, confidence=0.0, has_ink=False)

    reading = CellReading(has_ink=True)
    if is_probably_empty(cleaned):
        reading.reasons.append("ink too small to be a digit")
        return reading

    height = _largest_blob_height(cleaned)
    reading.ink_height = height

    vector = normalise_digit(cleaned)
    if vector is None:
        reading.reasons.append("could not be normalised")
        return reading

    _ensure_model()
    assert _samples is not None and _labels is not None

    distances = np.sum((_samples - vector) ** 2, axis=1)
    nearest = float(distances.min())
    reading.distance = nearest

    total = _samples.shape[0]
<<<<<<< HEAD
    k = min(K, total)
    idx = np.argpartition(distances, k - 1)[:k]
    near_labels = _labels[idx]
    near_dist = distances[idx]

    # Distance-weighted vote: closer templates count for more.  A clean glyph
    # lands on K identical templates and scores a full 1.0; an ambiguous one
    # splits its weight and is reported for review (or dropped below the floor).
    weights = 1.0 / (near_dist + 1e-6)
    class_weight = np.zeros(10, dtype=np.float64)
    np.add.at(class_weight, near_labels, weights)
    winner = int(class_weight.argmax())
    if winner < 1 or winner > 9:
        reading.reasons.append("no confident winner")
        return reading
    total_weight = float(class_weight.sum())
    confidence = float(class_weight[winner] / total_weight) if total_weight else 0.0
    if confidence < WEIGHTED_ACCEPT:
=======
    take = min(K * 3, total)
    idx = np.argpartition(distances, take - 1)[:take]
    neighbours = _labels[idx[np.argsort(distances[idx])[:K]]]
    winner = int(np.bincount(neighbours).argmax())
    if winner < 1 or winner > 9:
        reading.reasons.append("no confident winner")
        return reading
    confidence = float(np.count_nonzero(neighbours == winner)) / float(K)
    if confidence < MIN_SCORE:
>>>>>>> 8489722e6d638ec6bfd2c5806e03208df452060e
        reading.reasons.append("neighbours disagree")
        return reading

    reading.digit = winner
    reading.confidence = confidence
    return reading


def classify_cell(cell: np.ndarray) -> tuple[int, float]:
    """Return ``(digit, confidence)`` for a white-on-black cell patch."""
    reading = read_cell(cell)
    return reading.digit, reading.confidence


def split_into_cells(
    board_bin: np.ndarray, lattice=None, pad: int | None = None
) -> list[list[np.ndarray]]:
    """Cut a rectified board into 81 row-major cell patches.

    Boundaries come from the fitted :class:`~sudoku.image_processing.grid_detection.Lattice`
    when one is given (measured line positions, so slightly-off warps still
    segment correctly); otherwise a uniform split is assumed.  ``pad`` trims
    each cell edge so grid lines cannot bleed into the digit.
    """
    if board_bin is None or board_bin.size == 0:
        raise ValueError("Invalid board image")
    height, width = board_bin.shape[:2]
    if height < 160 or width != height:
        raise ValueError("Invalid board image")

    if lattice is None:
        row_edges = np.arange(10) * (height // 9)
        col_edges = np.arange(10) * (width // 9)
        row_edges[-1] = height
        col_edges[-1] = width
    else:
        row_edges = np.clip(np.round(lattice.rows).astype(int), 0, height)
        col_edges = np.clip(np.round(lattice.cols).astype(int), 0, width)

    if pad is None:
        cell_h = float(np.median(np.diff(row_edges)))
        cell_w = float(np.median(np.diff(col_edges)))
        pad = int(max(2, min(6, round(min(cell_h, cell_w) * 0.08))))
    pad = int(max(0, pad))

    cells: list[list[np.ndarray]] = []
    for row in range(9):
        line: list[np.ndarray] = []
        y1 = int(row_edges[row]) + pad
        y2 = int(row_edges[row + 1]) - pad
        if y2 - y1 < 4:
            y1, y2 = int(row_edges[row]), int(row_edges[row + 1])
        for col in range(9):
            x1 = int(col_edges[col]) + pad
            x2 = int(col_edges[col + 1]) - pad
            if x2 - x1 < 4:
                x1, x2 = int(col_edges[col]), int(col_edges[col + 1])
            line.append(board_bin[y1:y2, x1:x2].copy())
        cells.append(line)
    return cells


def recognize_digits(board_bin, lattice=None):
    """Classify every cell of a rectified board.

    Accepts a raw binary board (``lattice`` optional) or a
    :class:`~sudoku.image_processing.grid_detection.BoardPatch`.  Returns
    ``(grid, cell_confidence, uncertain_cells)``: the grid is a 9x9 matrix of
    integers (0 = empty), ``cell_confidence`` holds the k-NN agreement for
    each recognised digit (0.0 elsewhere), and ``uncertain_cells`` lists
    ``[row, col]`` pairs that hold ink but could not be read reliably.
    """
    binary = board_bin
    if hasattr(board_bin, "binary") and hasattr(board_bin, "lattice"):
        binary = board_bin.binary
        if lattice is None:
            lattice = board_bin.lattice

    cells = split_into_cells(binary, lattice)
    grid: list[list[int]] = [[0] * 9 for _ in range(9)]
    confidence: list[list[float]] = [[0.0] * 9 for _ in range(9)]
    readings: dict[tuple[int, int], CellReading] = {}

    for row in range(9):
        for col in range(9):
            reading = read_cell(cells[row][col])
            readings[(row, col)] = reading
            grid[row][col] = reading.digit
            confidence[row][col] = reading.confidence

    uncertain: list[list[int]] = [
        [row, col]
        for (row, col), reading in readings.items()
        if reading.has_ink and reading.digit == 0
    ]

    # Board-adaptive consistency checks.  A recognised digit must be
    # comparable in size to (and no farther from the training manifold than)
    # the other digits in *this* image.  Remnants that slipped through the
    # geometry gates are reported as uncertain instead of being kept as clues.
    kept = [reading for reading in readings.values() if reading.digit]
    heights = [reading.ink_height for reading in kept if reading.ink_height]
    distances = [reading.distance for reading in kept if np.isfinite(reading.distance)]
    median_height = float(np.median(heights)) if heights else 0.0
    median_distance = float(np.median(distances)) if distances else 0.0

    for (row, col), reading in readings.items():
        if not reading.digit:
            continue
        too_small = median_height > 0 and reading.ink_height < 0.55 * median_height
        too_far = (
            median_distance > 0
            and reading.distance
            > max(RELATIVE_DISTANCE_FACTOR * median_distance, RELATIVE_DISTANCE_FLOOR)
        )
        if not (too_small or too_far):
            continue
        grid[row][col] = 0
        confidence[row][col] = 0.0
        reading.digit = 0
        reading.confidence = 0.0
        reading.reasons.append(
            "much smaller than the other digits"
            if too_small
            else "far from every digit template"
        )
        if [row, col] not in uncertain:
            uncertain.append([row, col])

    return grid, confidence, uncertain
