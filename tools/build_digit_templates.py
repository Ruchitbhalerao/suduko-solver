"""Build the baked digit-template bank used by the k-NN classifier.

Run once (needs Pillow and a set of TrueType fonts available on the build
machine) to regenerate ``sudoku/image_processing/digit_templates.npz``.  The
shipped ``.npz`` is what the app loads at runtime, so no fonts are required in
production and recognition is identical on every machine.

    python tools/build_digit_templates.py

The bank combines OpenCV Hershey renders (robust to stroke-drawn inputs) with
digits rendered from common upright TrueType fonts at several sizes, weights
and print-like downscales -- the latter is what lets the classifier read real
printed/screenshot Sudoku boards, whose sans-serif glyphs the Hershey set alone
does not match.
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sudoku.image_processing.digit_recognition import (  # noqa: E402
    _training_set,
    normalise_digit,
)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    raise SystemExit("Pillow is required to build the template bank.")

_MPL = (
    "/Library/Frameworks/Python.framework/Versions/3.14/lib/python3.14/"
    "site-packages/matplotlib/mpl-data/fonts/ttf/"
)
_SUP = "/System/Library/Fonts/Supplemental/"
_FONT_NAMES = [
    "Arial.ttf", "Arial Bold.ttf", "Arial Narrow.ttf", "Arial Narrow Bold.ttf",
    "Arial Rounded Bold.ttf", "Arial Black.ttf", "Verdana.ttf", "Verdana Bold.ttf",
    "Tahoma.ttf", "Tahoma Bold.ttf", "Trebuchet MS.ttf", "Trebuchet MS Bold.ttf",
    "Georgia.ttf", "Georgia Bold.ttf", "Times New Roman.ttf", "Times New Roman Bold.ttf",
    "Courier New.ttf", "Courier New Bold.ttf", "Microsoft Sans Serif.ttf",
    "Comic Sans MS.ttf", "Comic Sans MS Bold.ttf",
]


def _font_paths() -> list[str]:
    paths = [p for p in (_SUP + n for n in _FONT_NAMES) if os.path.exists(p)]
    for extra in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
        if os.path.exists(_MPL + extra):
            paths.append(_MPL + extra)
    return paths


def _ttf_templates() -> tuple[list[np.ndarray], list[int]]:
    rng = np.random.default_rng(7)
    fonts = _font_paths()
    if not fonts:
        print("WARNING: no TrueType fonts found; bank will be Hershey-only.")
    vectors: list[np.ndarray] = []
    labels: list[int] = []
    for digit in range(1, 10):
        for path in fonts:
            for px in (40, 46, 52):
                try:
                    font = ImageFont.truetype(path, px)
                except Exception:
                    continue
                for mode in (0, 1, 2):          # normal / dilate / erode
                    # none / mild / strong downscale -- the strong tier is what
                    # matches digits on a modest-resolution printed board, where
                    # a glyph may be only ~14px tall.  Templates are kept upright:
                    # the Hershey set already carries rotated variants, and
                    # rotating the (far more numerous) TrueType templates as well
                    # pulled upright digits onto their tilted look-alikes.
                    for down in (0, 1, 2):
                        canvas = Image.new("L", (64, 64), 0)
                        draw = ImageDraw.Draw(canvas)
                        text = str(digit)
                        box = draw.textbbox((0, 0), text, font=font)
                        tw, th = box[2] - box[0], box[3] - box[1]
                        if tw == 0 or th == 0:
                            continue
                        draw.text(
                            ((64 - tw) // 2 - box[0], (64 - th) // 2 - box[1]),
                            text, fill=255, font=font,
                        )
                        img = np.array(canvas)
                        if mode == 1:
                            img = cv2.dilate(img, np.ones((2, 2), np.uint8))
                        elif mode == 2:
                            img = cv2.erode(img, np.ones((2, 2), np.uint8))
                        if down:
                            lo, hi = (16, 22) if down == 1 else (11, 16)
                            s = int(rng.integers(lo, hi))
                            img = cv2.resize(img, (s, s), interpolation=cv2.INTER_AREA)
                            img = cv2.resize(img, (64, 64), interpolation=cv2.INTER_LINEAR)
                        vec = normalise_digit((img > 90).astype(np.uint8) * 255)
                        if vec is not None:
                            vectors.append(vec.astype(np.float32))
                            labels.append(digit)
    return vectors, labels


def main() -> None:
    hershey_samples, hershey_labels = _training_set()
    ttf_vectors, ttf_labels = _ttf_templates()

    samples = np.vstack([hershey_samples, np.asarray(ttf_vectors, dtype=np.float32)])
    labels = np.concatenate(
        [hershey_labels, np.asarray(ttf_labels, dtype=np.int32)]
    ).astype(np.int16)

    # Quantise 0..1 features to uint8 to keep the shipped file small; the tiny
    # rounding error is immaterial to nearest-neighbour distances.
    quantised = np.clip(np.round(samples * 255.0), 0, 255).astype(np.uint8)

    out = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "sudoku", "image_processing", "digit_templates.npz",
    )
    np.savez_compressed(out, samples=quantised, labels=labels)
    size_mb = os.path.getsize(out) / 1e6
    print(f"wrote {out}")
    print(f"templates: {len(labels)}  (Hershey {len(hershey_labels)} + TTF {len(ttf_labels)})")
    print(f"file size: {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
