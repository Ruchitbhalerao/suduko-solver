from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
from django.test import SimpleTestCase
from django.urls import reverse

from sudoku.image_processing import SudokuExtractionError, extract_sudoku_from_image

EXAMPLE = [
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


def _load_fixture(name: str) -> bytes:
    return Path(f"sudoku/tests/fixtures_images/{name}").read_bytes()


def _img_to_png(img: np.ndarray) -> bytes:
    _, enc = cv2.imencode(".png", img)
    return enc.tobytes()


class ImageRecognitionPipelineTests(SimpleTestCase):
    def test_extract_from_fixture_plain(self):
        res = extract_sudoku_from_image(_load_fixture("example_board_plain.png"))
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["recognized_cells"], 30)
        self.assertEqual(res["grid"], EXAMPLE)

    def test_no_grid_detected_blank(self):
        img = np.full((300, 300, 3), 255, np.uint8)
        with self.assertRaises(SudokuExtractionError) as cm:
            extract_sudoku_from_image(_img_to_png(img))
        self.assertEqual(cm.exception.code, "no_grid_detected")

    def test_missing_image(self):
        with self.assertRaises(SudokuExtractionError) as cm:
            extract_sudoku_from_image(b"")
        self.assertEqual(cm.exception.code, "missing_image")

    def test_corrupt_image(self):
        with self.assertRaises(SudokuExtractionError):
            extract_sudoku_from_image(b"not an image at all")


class ImageRecognitionApiTests(SimpleTestCase):
    def setUp(self):
        self.url = reverse("sudoku:api_extract_sudoku")

    def test_extract_via_api(self):
        f = io.BytesIO(_load_fixture("example_board_plain.png"))
        f.name = "sudoku.png"
        resp = self.client.post(self.url, {"image": f}, format="multipart")
        self.assertEqual(resp.status_code, 200)
        j = resp.json()
        self.assertEqual(j["status"], "ok")
        self.assertEqual(j["recognized_cells"], 30)
        self.assertEqual(j["grid"], EXAMPLE)

    def test_missing_image_api(self):
        resp = self.client.post(self.url, {}, format="multipart")
        self.assertEqual(resp.status_code, 400)
        j = resp.json()
        self.assertEqual(j["status"], "missing_image")

    def test_invalid_image_api(self):
        f = io.BytesIO(b"not an image")
        f.name = "bad.png"
        resp = self.client.post(self.url, {"image": f}, format="multipart")
        self.assertEqual(resp.status_code, 422)
        j = resp.json()
        self.assertEqual(j["status"], "invalid_image")

    def test_get_method_not_allowed(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_unsupported_extension(self):
        f = io.BytesIO(b"GIF89a")
        f.name = "bad.gif"
        resp = self.client.post(self.url, {"image": f}, format="multipart")
        self.assertIn(resp.status_code, (415, 422))
