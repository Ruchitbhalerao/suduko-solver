"""Image loading and low-level conditioning for the recognition pipeline.

Responsibilities: decode, size limits, aspect-preserving resize, grayscale,
denoising and binarisation.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# Operational limits. The API layer enforces the byte-size limit as well; the
# pixel limit keeps a decompression bomb from exhausting memory.
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB
MAX_PIXELS = 40_000_000
DEFAULT_MAX_SIDE = 1600


class ImageDecodeError(ValueError):
    """Raised when the uploaded bytes are not a decodable image."""


@dataclass
class LoadedImage:
    color: np.ndarray
    gray: np.ndarray
    binary: np.ndarray


def load_image(image_bytes: bytes) -> np.ndarray:
    """Decode image bytes into a colour BGR array."""
    if not image_bytes:
        raise ImageDecodeError("The uploaded file is empty.")
    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    if buffer.size == 0:
        raise ImageDecodeError("The uploaded file is empty.")
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ImageDecodeError(
            "The file could not be read as an image. Supported formats are "
            "PNG, JPEG and WEBP."
        )
    if image.shape[0] < 64 or image.shape[1] < 64:
        raise ImageDecodeError("The image is too small to contain a Sudoku grid.")
    if image.shape[0] * image.shape[1] > MAX_PIXELS:
        raise ImageDecodeError("The image dimensions are too large.")
    return image


def resize_with_aspect_ratio(image: np.ndarray, max_side: int = DEFAULT_MAX_SIDE) -> np.ndarray:
    """Shrink large images so the longest edge is ``max_side``."""
    if image is None or image.size == 0:
        return image
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= max_side:
        return image
    scale = max_side / float(longest)
    return cv2.resize(
        image,
        (max(1, int(round(width * scale))), max(1, int(round(height * scale)))),
        interpolation=cv2.INTER_AREA,
    )


def to_grayscale(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def denoise(gray: np.ndarray) -> np.ndarray:
    return cv2.bilateralFilter(gray, 7, 60, 60)


def binarize(gray: np.ndarray) -> np.ndarray:
    """Adaptive threshold so uneven photo lighting does not hide the grid.

    A relatively large window with a small constant keeps thick digit strokes
    solid (a small window would hollow them out) while still tracking lighting
    gradients across a photograph.
    """
    side = min(gray.shape[:2])
    block = 25 if side >= 200 else 11
    if block % 2 == 0:
        block += 1
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, block, 10
    )
    # Close hairline gaps in the grid lines so the outline forms one contour.
    kernel = np.ones((3, 3), np.uint8)
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)


def preprocess(image_bytes: bytes, max_side: int = DEFAULT_MAX_SIDE) -> LoadedImage:
    """Decode, resize, grayscale, denoise and binarise an uploaded image."""
    color = load_image(image_bytes)
    color = resize_with_aspect_ratio(color, max_side)
    gray = denoise(to_grayscale(color))
    return LoadedImage(color=color, gray=gray, binary=binarize(gray))
