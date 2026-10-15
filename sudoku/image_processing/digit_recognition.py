"""Digit classification for extracted Sudoku cells.

Approach
--------
A small k-nearest-neighbours classifier trained *locally*, at import time, on
synthetic digits rendered with OpenCV's Hershey fonts at several sizes,
thicknesses and offsets, with light morphological and noise augmentation.
Only NumPy is needed for the classifier itself (OpenCV 5 no longer ships the
``cv2.ml`` module), so there is no model file to download, no paid service and
no large runtime dependency.

Confidence is the fraction of the ``k`` nearest training samples that voted for
the winning digit. That is a genuine, reproducible statistic rather than an
invented number; it is only reported for cells that actually contain ink.
"""

from __future__ import annotations

import threading

import cv2
import numpy as np

CANVAS = 28
CROP = 20  # digit fitted into a 20x20 box centred on a 28x28 canvas
FEATURES = CANVAS * CANVAS
K = 5
MIN_SCORE = 0.6  # below this a cell is reported as unknown

_FONTS = (
    cv2.FONT_HERSHEY_SIMPLEX,
    cv2.FONT_HERSHEY_PLAIN,
    cv2.FONT_HERSHEY_DUPLEX,
    cv2.FONT_HERSHEY_COMPLEX,
    cv2.FONT_HERSHEY_TRIPLEX,
    cv2.FONT_HERSHEY_COMPLEX_SMALL,
)

_lock = threading.Lock()
_samples: np.ndarray | None = None
_labels: np.ndarray | None = None


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
            shift: int, rng: np.random.Generator) -> np.ndarray | None:
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

    variant = int(rng.integers(0, 4))
    if variant == 1:
        img = cv2.erode(img, np.ones((2, 2), np.uint8))
    elif variant == 2:
        img = cv2.dilate(img, np.ones((2, 2), np.uint8))

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
                    for _ in range(5):
                        vec = _render(digit, font, scale, thickness, 3, rng)
                        if vec is not None:
                            samples.append(vec)
                            labels.append(digit)
    return np.vstack(samples), np.asarray(labels, dtype=np.int32)


def _ensure_model() -> None:
    global _samples, _labels
    if _samples is None:
        with _lock:
            if _samples is None:
                samples, labels = _training_set()
                _samples = np.ascontiguousarray(samples, dtype=np.float32)
                _labels = labels


def is_probably_empty(cell: np.ndarray) -> bool:
    """True when a cell patch holds no usable ink."""
    if cell is None or getattr(cell, "size", 0) == 0:
        return True
    binary = (np.asarray(cell) > 127).astype(np.uint8)
    total = int(binary.size)
    if total == 0:
        return True
    # ``binary`` is 0/1, so its sum is simply the lit-pixel count.
    if int(binary.sum()) < max(12.0, total * 0.03):
        return True
    num, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if num <= 1:
        return True
    areas = stats[1:, cv2.CC_STAT_AREA]
    return float(areas.max()) < max(12.0, total * 0.015)


def classify_cell(cell: np.ndarray) -> tuple[int, float]:
    """Return ``(digit, confidence)`` for a white-on-black cell patch."""
    if is_probably_empty(cell):
        return 0, 0.0
    vector = normalise_digit(cell)
    if vector is None:
        return 0, 0.0
    _ensure_model()
    assert _samples is not None and _labels is not None

    distances = np.sum((_samples - vector) ** 2, axis=1)
    # Partial selection keeps this cheap for a few thousand training samples.
    total = _samples.shape[0]
    take = min(K * 3, total)
    idx = np.argpartition(distances, take - 1)[:take]
    neighbours = _labels[idx[np.argsort(distances[idx])[:K]]]
    winner = int(np.bincount(neighbours).argmax())
    if winner < 1 or winner > 9:
        return 0, 0.0
    confidence = float(np.count_nonzero(neighbours == winner)) / float(K)
    return winner, confidence


def split_into_cells(board_bin: np.ndarray) -> list[list[np.ndarray]]:
    """Cut a rectified board into 81 row-major cell patches."""
    if board_bin is None or board_bin.size == 0:
        raise ValueError("Invalid board image")
    side = int(board_bin.shape[0])
    if side < 180 or board_bin.shape[1] != side:
        raise ValueError("Invalid board image")
    step = side // 9
    cells: list[list[np.ndarray]] = []
    for row in range(9):
        line: list[np.ndarray] = []
        for col in range(9):
            # Trim the cell edges so grid lines do not bleed into the digit.
            pad = 3
            y1, y2 = row * step + pad, (row + 1) * step - pad
            x1, x2 = col * step + pad, (col + 1) * step - pad
            line.append(board_bin[y1:y2, x1:x2].copy())
        cells.append(line)
    return cells


def recognize_digits(board_bin: np.ndarray) -> tuple[list[list[int]], list[list[float]]]:
    """Classify every cell of a rectified board.

    Returns ``(grid, cell_confidence)`` where ``grid`` is a 9x9 matrix of
    integers (0 = empty) and ``cell_confidence`` holds the k-NN agreement for
    each recognised digit (0.0 for cells with no digit).
    """
    cells = split_into_cells(board_bin)
    grid: list[list[int]] = [[0] * 9 for _ in range(9)]
    confidence: list[list[float]] = [[0.0] * 9 for _ in range(9)]
    for row in range(9):
        for col in range(9):
            digit, score = classify_cell(cells[row][col])
            grid[row][col] = digit
            confidence[row][col] = score
    return grid, confidence
