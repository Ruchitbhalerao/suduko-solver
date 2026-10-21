"""Locate and rectify the Sudoku board inside a thresholded image.

The pipeline here no longer asks "does this patch contain ten equally spaced
lines at *exactly* the assumed positions?".  Instead it *fits* the lattice:
line positions are measured from the image, a uniform 10-line model is scored
against those measurements, and the fitted model becomes the authority for
cell boundaries.  This is what makes slightly-off quads, margin-padded crops
and degraded (partially broken) grid lines recoverable instead of fatal.

If the first pass over the untouching contour candidates fails, a small
rotation sweep re-runs detection on tilted copies of the image.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

MIN_BOARD_AREA = 10000
GRID_LINES = 10

# A grid line is a peak in the projection profile; the adaptive threshold
# picks peaks rising this far above the local baseline.  It is deliberately
# small: on a faint board the thin cell lines reach only a third of the thick
# 3x3 lines, and a larger fraction would hide them entirely.
PEAK_FRACTION = 0.15

# Rotation angles (degrees) tried when the untilted image yields no lattice.
_FALLBACK_ANGLES = (5.0, -5.0, 10.0, -10.0, 15.0, -15.0)

# Finer sweep used when the lattice exists but has poor quality (rotated
# board).  Step of 1° keeps the search cheap (21 calls to _search).
_SWEEP_ANGLES = tuple(np.arange(-12.0, 12.5, 1.0))


@dataclass(frozen=True)
class Lattice:
    """Measured positions of the ten grid lines in each direction.

    ``rows`` holds y positions of horizontal lines and ``cols`` x positions of
    vertical lines, both ascending and both of length ten.  ``row_score`` and
    ``col_score`` count the measurements that support the fitted model.
    """

    rows: np.ndarray
    cols: np.ndarray
    row_score: int
    col_score: int

    @property
    def cell_height(self) -> float:
        return float(np.median(np.diff(self.rows)))

    @property
    def cell_width(self) -> float:
        return float(np.median(np.diff(self.cols)))

    @property
    def step(self) -> float:
        return float(min(self.cell_width, self.cell_height))

    @property
    def score(self) -> int:
        return int(self.row_score + self.col_score)


def _lattice_ink_quality(patch: np.ndarray, lattice: Lattice) -> float:
    """Fraction of the patch's ink that lies near a lattice line.

    A correctly rectified board concentrates its dark pixels (grid lines and
    digit strokes) around the fitted lattice rulings.  When the grid is
    still diagonal after the perspective warp, the fitter can produce a
    plausible-looking lattice from smeared projection peaks, but the actual
    ink will not align with the fitted line positions — most of it falls
    *between* the lines.  This metric exposes that difference: values close
    to 1.0 mean the lattice lines sit on the ink; values near 0.5 mean the
    ink is evenly spread (a wrong lattice).
    """
    if patch is None or patch.size == 0 or patch.ndim != 2:
        return 0.0
    side = patch.shape[0]
    ink = (patch > 127).astype(np.uint8)
    total = int(cv2.countNonZero(ink))
    if total == 0:
        return 0.0

    tolerance = max(2, int(round(0.03 * side)))
    mask = np.zeros_like(ink)
    for y in np.round(lattice.rows).astype(int):
        y0, y1 = max(0, y - tolerance), min(side, y + tolerance + 1)
        mask[y0:y1, :] = 1
    for x in np.round(lattice.cols).astype(int):
        x0, x1 = max(0, x - tolerance), min(side, x + tolerance + 1)
        mask[:, x0:x1] = 1
    near = int(cv2.countNonZero(cv2.bitwise_and(ink, mask)))
    return near / total


@dataclass(frozen=True)
class BoardPatch:
    """A rectified board: line-cleaned pixels plus the fitted cell lattice."""

    binary: np.ndarray
    lattice: Lattice
    angle: float = 0.0


def order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as top-left, top-right, bottom-right, bottom-left."""
    pts = np.asarray(pts, dtype="float32").reshape(4, 2)
    summed = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).reshape(-1)
    rect = np.zeros((4, 2), dtype="float32")
    rect[0] = pts[np.argmin(summed)]
    rect[2] = pts[np.argmax(summed)]
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _quadrilateral_candidates(img_bin: np.ndarray) -> list[np.ndarray]:
    """Approximate candidate outlines, most-square first."""
    contours, _ = cv2.findContours(img_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:8]

    candidates: list[np.ndarray] = []
    for contour in contours:
        if cv2.contourArea(contour) < MIN_BOARD_AREA:
            break
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        for epsilon in (0.01, 0.02, 0.03, 0.05, 0.08):
            approx = cv2.approxPolyDP(contour, epsilon * perimeter, True)
            if len(approx) == 4:
                candidates.append(approx)
                break
        else:
            # A rotated board outline: use the minimum-area rectangle corners.
            box = cv2.minAreaRect(contour)
            rect = cv2.boxPoints(box)
            if cv2.contourArea(rect) >= MIN_BOARD_AREA:
                candidates.append(rect.reshape(4, 1, 2).astype(np.float32))
    return candidates


def _looks_like_board(candidate: np.ndarray) -> bool:
    """A board outline should be a reasonably large, roughly equilateral shape."""
    rect = order_points(candidate)
    (tl, tr, br, bl) = rect
    width = np.linalg.norm(tr - tl)
    height = np.linalg.norm(bl - tl)
    if width <= 1 or height <= 1:
        return False
    if width * height < MIN_BOARD_AREA:
        return False
    # Perspective photos skew the aspect, but not beyond roughly 3:1.
    aspect = max(width, height) / min(width, height)
    if aspect > 3.5:
        return False
    # Reject shapes that are almost degenerate (slivers).
    diagonal = np.linalg.norm(br - tl)
    if diagonal <= 0:
        return False
    area = float(width * height)
    return area >= 0.45 * (diagonal ** 2) * 0.5


def find_board_corners(img_bin: np.ndarray) -> np.ndarray | None:
    for candidate in _quadrilateral_candidates(img_bin):
        if _looks_like_board(candidate):
            return np.asarray(candidate, dtype="float32")
    return None


def perspective_transform(img: np.ndarray, corners: np.ndarray, side: int = 450) -> np.ndarray:
    rect = order_points(corners)
    dst = np.array(
        [[0, 0], [side - 1, 0], [side - 1, side - 1], [0, side - 1]], dtype="float32"
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img, matrix, (side, side))


def _expand_quad(corners: np.ndarray, factor: float = 1.05) -> np.ndarray:
    """Push each corner of a quad outward from its centre by ``factor``.

    Contour detection on a rotated board often finds corners just inside the
    outer border, which clips the border grid lines during the perspective
    warp.  Without those border lines the lattice fitter sees only the inner
    rulings and fits a wrong cell size.
    """
    rect = order_points(corners).astype("float32")
    centre = rect.mean(axis=0, keepdims=True)
    return (centre + (rect - centre) * factor).astype("float32")


# ---------------------------------------------------------------------------
# Lattice fitting
# ---------------------------------------------------------------------------


def _smooth(profile: np.ndarray, width: int) -> np.ndarray:
    width = max(3, width | 1)
    pad = width // 2
    padded = np.pad(profile.astype(np.float64), pad, mode="edge")
    kernel = np.ones(width, dtype=np.float64) / width
    return np.convolve(padded, kernel, mode="valid")


def _profile_peaks(profile: np.ndarray, side: int) -> np.ndarray:
    """Positions of the strongest local maxima (candidate grid-line centres).

    Only a 3px box filter is applied: grid lines are often a single pixel
    wide after thresholding, and a wider average would bury them under the
    very baseline this function is trying to rise above.
    """
    smoothed = _smooth(profile, 3)
    baseline = float(np.median(smoothed))
    peak = float(smoothed.max())
    if peak <= baseline + 1:
        return np.array([], dtype=np.float64)
    # Adaptive threshold: strong lines must stand out of the *local* baseline,
    # so a noisy photograph (high baseline) does not hide them behind a fixed
    # absolute cut-off the way the old 0.45*side rule did.
    threshold = baseline + 0.35 * (peak - baseline)

    window = max(3, side // 60)
    peaks: list[int] = []
    for index in range(len(smoothed)):
        value = smoothed[index]
        if value < threshold:
            continue
        lo = max(0, index - window)
        hi = min(len(smoothed), index + window + 1)
        if value >= smoothed[lo:hi].max():
            peaks.append(index)
    if not peaks:
        return np.array([], dtype=np.float64)

    # Collapse runs of adjacent indices (plateaus) into a single peak.
    groups: list[list[int]] = [[peaks[0]]]
    for index in peaks[1:]:
        if index - groups[-1][-1] <= window:
            groups[-1].append(index)
        else:
            groups.append([index])
    centres = [
        float(group[int(np.argmax(smoothed[group]))]) for group in groups
    ]
    return np.asarray(centres, dtype=np.float64)


def _fit_axis(peaks: np.ndarray, side: int) -> tuple[float, float, int] | None:
    """Fit ``origin + k*step`` (k = 0..9) to the measured peaks.

    Returns ``(origin, step, inliers)`` for the best model that both spans a
    plausible fraction of the patch and keeps every model point inside it, or
    ``None`` when no model is convincing.  A board whose thin lines vanished
    but whose thick 3x3 lines survived still fits: the border-plus-two-inner
    model explains four peaks at exactly 1/3 spacing.
    """
    if peaks.size < 3:
        return None

    # A Sudoku cell is roughly side/9 wide.  Allow ±25% slack for imperfect
    # crops, but reject sub-grids (e.g. fitting every other line gives a step
    # of side/18 — far too small to be a real cell).
    step_lo = side * 0.75 / 9.0
    step_hi = side * 1.25 / 9.0

    steps: set[float] = set()
    for i in range(peaks.size):
        for j in range(i + 1, peaks.size):
            gap = peaks[j] - peaks[i]
            for divisor in range(1, GRID_LINES):
                step = gap / divisor
                if step_lo <= step <= step_hi:
                    steps.add(round(step, 2))
    if not steps:
        return None

    ks = np.arange(GRID_LINES, dtype=np.float64)
    best: tuple[float, float, int] | None = None
    best_score = -1.0
    best_residual = float("inf")
    for step in sorted(steps):
        span = (GRID_LINES - 1) * step
        # Every peak is a plausible line k for some origin; try all of them.
        origins = (peaks[:, None] - ks[None, :] * step).ravel()
        origins = np.unique(np.round(origins, 1))
        # The board's outer border sits at the edge of a rectified patch, so a
        # genuine lattice both starts and ends near the patch boundaries.  A
        # model living in the middle (e.g. 157..413 of 450) is a sub-structure
        # -- half a board, one 3x3 block -- and must not win.
        ends = origins + span
        keep = (origins >= -0.02 * side) & (origins <= 0.13 * side) & (
            ends >= 0.87 * side
        ) & (ends <= 1.02 * side)
        origins = origins[keep]
        if origins.size == 0:
            continue
        centres = origins[:, None] + ks[None, :] * step
        tolerance = 0.3 * step
        distances = np.abs(centres[:, :, None] - peaks[None, None, :])
        hit = distances <= tolerance
        inliers = hit.any(axis=2).sum(axis=1)
        # Every real Sudoku board has an outer border on both ends.
        near_first = hit[:, 0, :].any(axis=1)
        near_last = hit[:, -1, :].any(axis=1)
        # Accept either a dense lattice (most lines measured) or a sparse but
        # fully-bordered one (only the thick 3x3 lines survived thresholding).
        acceptable = ((inliers >= 6) & (near_first | near_last)) | (
            (inliers >= 4) & near_first & near_last
        )
        if not acceptable.any():
            continue
        # How tightly the measured peaks hug the model, for tie-breaking:
        # two steps can explain the same peaks, but only the true one has the
        # smallest cumulative residual (a wrong step drifts at the far end).
        residual = distances.min(axis=2).sum(axis=1)
        score = np.where(acceptable, inliers + 0.5 * (near_first + near_last), -1.0)
        for index in np.argsort(-score):
            if score[index] < best_score:
                break
            if score[index] > best_score or residual[index] < best_residual:
                best_score = float(score[index])
                best_residual = float(residual[index])
                best = (float(origins[index]), float(step), int(inliers[index]))

    return best


def fit_lattice(patch: np.ndarray) -> Lattice | None:
    """Fit a 10x10 line lattice to a rectified board patch, or ``None``."""
    if patch is None or patch.size == 0:
        return None
    side = patch.shape[0]
    if patch.ndim != 2:
        patch = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
    if side < 160 or patch.shape[1] != side:
        return None

    column_profile = patch.sum(axis=0).astype(np.float64) / 255.0
    row_profile = patch.sum(axis=1).astype(np.float64) / 255.0

    col_fit = _fit_axis(_profile_peaks(column_profile, side), side)
    row_fit = _fit_axis(_profile_peaks(row_profile, side), side)
    if col_fit is None or row_fit is None:
        return None

    col_origin, col_step, col_inliers = col_fit
    row_origin, row_step, row_inliers = row_fit
    # Both directions must agree on the cell size, otherwise two unrelated
    # structures were fitted.
    if abs(col_step - row_step) > 0.2 * min(col_step, row_step):
        return None

    return Lattice(
        rows=np.clip(row_origin + np.arange(GRID_LINES) * row_step, 0, side - 1),
        cols=np.clip(col_origin + np.arange(GRID_LINES) * col_step, 0, side - 1),
        row_score=row_inliers,
        col_score=col_inliers,
    )


def looks_like_grid(board: np.ndarray) -> bool:
    """Backwards-compatible wrapper: True when a lattice can be fitted."""
    return fit_lattice(board) is not None


# ---------------------------------------------------------------------------
# Rectification
# ---------------------------------------------------------------------------


def _rotate(img: np.ndarray, angle: float) -> np.ndarray:
    """Rotate an image about its centre without clipping the content.

    A plain ``warpAffine`` rotates into a canvas of the same size, which
    cuts off the corners — fatal when the board fills most of the frame.
    The image is first padded by 20% of its diagonal so the full content
    survives any rotation up to 45°.
    """
    height, width = img.shape[:2]
    pad = int(0.20 * np.hypot(width, height))
    padded = cv2.copyMakeBorder(
        img, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0
    )
    ph, pw = padded.shape[:2]
    matrix = cv2.getRotationMatrix2D((pw / 2, ph / 2), angle, 1.0)
    rotated = cv2.warpAffine(
        padded, matrix, (pw, ph), flags=cv2.INTER_LINEAR, borderValue=0
    )
    return rotated


def _search(img_bin: np.ndarray, side: int) -> tuple[np.ndarray, Lattice] | None:
    """Try every plausible quad on one (possibly rotated) binary image.

    For each quad candidate the patch is perspective-transformed to a square
    and a lattice is fitted.  If the fitted lattice misses the border lines
    (the outermost rulings are far from the patch edges — a sign that
    contour detection found corners just inside the board border), the quad
    is expanded outward and the fit retried.
    """
    best: tuple[np.ndarray, Lattice] | None = None
    best_quality = -1.0
    for candidate in _quadrilateral_candidates(img_bin):
        if not _looks_like_board(candidate):
            continue

        patch = perspective_transform(img_bin, candidate, side=side)
        if patch is None or patch.size == 0:
            continue
        ink = float(cv2.countNonZero(patch)) / float(patch.size)
        if ink < 0.008 or ink > 0.7:
            continue

        lattice = fit_lattice(patch)

        # If the lattice misses the border lines, the quad likely clipped
        # them.  Expand the quad outward and retry.
        if lattice is not None and not _lattice_spans_patch(lattice, side):
            expanded = perspective_transform(
                img_bin, _expand_quad(candidate), side=side
            )
            if expanded is not None and expanded.size > 0:
                expanded_lattice = fit_lattice(expanded)
                if expanded_lattice is not None and _lattice_spans_patch(
                    expanded_lattice, side
                ):
                    patch = expanded
                    lattice = expanded_lattice

        if lattice is not None:
            quality = _lattice_quality(patch, lattice, side)
            if quality > best_quality:
                best_quality = quality
                best = (patch, lattice)
    return best


def _lattice_quality(patch: np.ndarray, lattice: Lattice, side: int) -> float:
    """Overall quality of a fitted lattice: ink alignment + span + step.

    A correct lattice scores close to 1.0; a sub-grid or diagonal-line fit
    scores well below that.  This single metric drives both the quad
    comparison inside :func:`_search` and the rotation-retry decision in
    :func:`extract_board`.
    """
    ink = _lattice_ink_quality(patch, lattice)
    span = 1.0 if _lattice_spans_patch(lattice, side) else 0.0
    step_ratio = lattice.step / (side / 9.0)
    step_match = float(np.exp(-4.0 * abs(step_ratio - 1.0)))
    return ink + 0.3 * span + 0.5 * step_match


def _lattice_spans_patch(lattice: Lattice, side: int) -> bool:
    """True when the outermost lattice lines are near the patch edges.

    A correctly rectified board has its border rulings at the very edge of
    the square patch.  If the first/last lines are far inside, the contour
    detection clipped the border and the quad needs expanding.
    """
    rows, cols = lattice.rows, lattice.cols
    margin = 0.06 * side  # allow up to 6% inset for imperfect crops
    return (
        rows[0] <= margin
        and rows[-1] >= side - 1 - margin
        and cols[0] <= margin
        and cols[-1] >= side - 1 - margin
    )


def remove_grid_lines(board: np.ndarray, lattice: Lattice | None = None) -> np.ndarray:
    """Strip the grid's ruling so only digit strokes remain.

    Grid lines are much longer than any digit stroke, so a morphological
    opening with a kernel close to one cell wide isolates them; the result is
    dilated slightly and subtracted from the board.  When a lattice is known
    its measured cell size sets the kernel length instead of ``side // 9``.

    After the bulk removal a second pass removes *residual fragments*: short
    segments of a broken or slightly-diagonal line that survived the opening.
    These are identified purely on geometry — a component that is long and
    thin (spanning most of the cell in one direction while being only a few
    pixels wide in the other) is a line remnant, never a digit stroke.
    """
    if board is None or board.size == 0:
        return board

    height, width = board.shape[:2]
    result = board.copy()

    # --- pass 1: morphological opening ---
    if lattice is not None:
        length = max(3, int(lattice.step * 0.9))
    else:
        length = max(3, int(height // 9 * 0.9))
    horizontal = cv2.morphologyEx(
        result, cv2.MORPH_OPEN, np.ones((1, length), np.uint8)
    )
    vertical = cv2.morphologyEx(
        result, cv2.MORPH_OPEN, np.ones((length, 1), np.uint8)
    )
    lines = cv2.bitwise_or(horizontal, vertical)
    lines = cv2.dilate(lines, np.ones((3, 3), np.uint8), iterations=1)
    result = cv2.bitwise_and(result, cv2.bitwise_not(lines))

    # --- pass 2: remove residual line fragments ---
    # After the morphological opening, short segments of broken or slightly
    # diagonal lines can survive.  These are identified purely on geometry:
    # a component that is thin (1-3 px) in one axis while having any
    # significant length in the other is a line remnant, never a digit.
    # Digits are always wider than 3 px in both directions (even a "1"
    # rendered with Hershey fonts has a horizontal foot or serif).
    cell_h = lattice.step if lattice is not None else height / 9.0
    cell_w = lattice.step if lattice is not None else width / 9.0
    max_line_thickness = max(3, int(round(0.06 * min(cell_h, cell_w))))
    min_line_length = max(8, int(round(0.25 * max(cell_h, cell_w))))
    num, labels, stats, _ = cv2.connectedComponentsWithStats(
        (result > 127).astype(np.uint8), connectivity=8
    )
    if num > 1:
        drop = np.zeros(num, dtype=bool)
        for index in range(1, num):
            w = int(stats[index][cv2.CC_STAT_WIDTH])
            h = int(stats[index][cv2.CC_STAT_HEIGHT])
            area = int(stats[index][cv2.CC_STAT_AREA])
            if area < 6:
                continue
            thin_horizontal = h <= max_line_thickness and w >= min_line_length
            thin_vertical = w <= max_line_thickness and h >= min_line_length
            if thin_horizontal or thin_vertical:
                drop[index] = True
        if drop.any():
            result[drop[labels]] = 0

    return result


def extract_board(img_bin: np.ndarray, side: int = 450) -> BoardPatch | None:
    """Locate, rectify and clean the board, or return ``None``.

    The returned :class:`BoardPatch` carries the line-removed pixels *and* the
    lattice that was measured from the image, so downstream cell segmentation
    uses measured boundaries rather than an assumed uniform split.

    When the lattice fitted on the untilted image is poor (rotated board:
    the perspective warp leaves the internal grid lines diagonal, yielding a
    sub-grid or a lattice with bad ink alignment), the *original binary
    image* is rotated and the full search re-run.  Rotating the source is
    essential — rotating the already-rectified patch cannot undo the
    diagonal grid left by the perspective warp.
    """
    if img_bin is None or img_bin.size == 0:
        return None

    found = _search(img_bin, side)
    angle = 0.0
    if found is not None:
        patch, lattice = found
        if _lattice_quality(patch, lattice, side) < 1.1:
            # Quality is marginal or poor; try rotating the original image.
            best = found
            best_quality = _lattice_quality(patch, lattice, side)
            for fallback in _SWEEP_ANGLES:
                candidate = _search(_rotate(img_bin, float(fallback)), side)
                if candidate is None:
                    continue
                cpatch, clattice = candidate
                quality = _lattice_quality(cpatch, clattice, side)
                if quality > best_quality:
                    best_quality = quality
                    best = candidate
                    angle = float(fallback)
            found = best
    else:
        for fallback in _FALLBACK_ANGLES:
            found = _search(_rotate(img_bin, fallback), side)
            if found is not None:
                angle = fallback
                break
    if found is None:
        return None

    patch, lattice = found
    return BoardPatch(
        binary=remove_grid_lines(patch, lattice),
        lattice=lattice,
        angle=angle,
    )
