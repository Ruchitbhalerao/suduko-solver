"""Locate and rectify the Sudoku board inside a thresholded image."""

from __future__ import annotations

import cv2
import numpy as np

MIN_BOARD_AREA = 10000


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


def remove_grid_lines(board: np.ndarray) -> np.ndarray:
    """Strip the grid's ruling so only digit strokes remain.

    Grid lines are much longer than any digit stroke, so a morphological
    opening with a kernel close to one cell wide isolates them; the result is
    dilated slightly and subtracted from the board.
    """
    if board is None or board.size == 0:
        return board
    step = board.shape[0] // 9
    length = max(3, int(step * 0.9))
    horizontal = cv2.morphologyEx(
        board, cv2.MORPH_OPEN, np.ones((1, length), np.uint8)
    )
    vertical = cv2.morphologyEx(
        board, cv2.MORPH_OPEN, np.ones((length, 1), np.uint8)
    )
    lines = cv2.bitwise_or(horizontal, vertical)
    lines = cv2.dilate(lines, np.ones((3, 3), np.uint8), iterations=1)
    return cv2.bitwise_and(board, cv2.bitwise_not(lines))


def extract_board(img_bin: np.ndarray, side: int = 450) -> np.ndarray | None:
    """Return a rectified square patch of the detected board, or ``None``."""
    if img_bin is None or img_bin.size == 0:
        return None
    corners = find_board_corners(img_bin)
    if corners is None:
        return None
    board = perspective_transform(img_bin, corners, side=side)
    if board is None or board.size == 0:
        return None
    # A detection that is mostly ink means we grabbed a block, not a grid.
    ink = float(cv2.countNonZero(board)) / float(board.size)
    if ink < 0.01 or ink > 0.6:
        return None
    if not looks_like_grid(board):
        return None
    return remove_grid_lines(board)


def looks_like_grid(board: np.ndarray) -> bool:
    """Sanity-check a rectified board by looking for the 10x10 line lattice.

    A warped patch can be a plausible quadrilateral yet not be a Sudoku board
    (clipped corners, a plain rectangle on a photo, and so on). Rejecting those
    here keeps garbage digits from ever reaching the client.
    """
    if board is None or board.size == 0:
        return False
    height, width = board.shape[:2]
    if height < 180 or width < 180 or abs(height - width) > 4:
        return False

    side = min(height, width)
    step = side // 9

    def _line_strength(profile: np.ndarray) -> int:
        """How many expected grid lines are strongly present."""
        found = 0
        for index in range(10):
            centre = index * step
            if index == 9:
                centre = side - 2
            lo = max(0, centre - 4)
            hi = min(side, centre + 5)
            if hi <= lo:
                continue
            window = profile[lo:hi]
            if float(window.max()) >= 0.45 * side:
                found += 1
        return found

    vertical = _line_strength(board.sum(axis=0).astype(np.float32) / 255.0)
    horizontal = _line_strength(board.sum(axis=1).astype(np.float32) / 255.0)
    return vertical >= 7 and horizontal >= 7
