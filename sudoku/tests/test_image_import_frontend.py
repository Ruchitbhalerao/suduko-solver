from __future__ import annotations

import io
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse

from sudoku.tests.test_image_recognition import EXAMPLE, _load_fixture


class ImageImportFrontendTests(SimpleTestCase):
    def test_home_has_upload_section(self):
        resp = self.client.get(reverse("sudoku:placeholder"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")
        self.assertIn('id="upload-dropzone"', content)
        self.assertIn('id="extract-button"', content)
        self.assertIn('id="reset-image-button"', content)
        self.assertIn('data-extract-url="/api/extract-sudoku/"', content)

    def test_extract_roundtrip_via_api(self):
        url = reverse("sudoku:api_extract_sudoku")
        f = io.BytesIO(_load_fixture("example_board_plain.png"))
        f.name = "s.png"
        resp = self.client.post(url, {"image": f}, format="multipart")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["grid"], EXAMPLE)

        solve = reverse("sudoku:api_solve")
        for alg in ("backtracking", "mrv", "mrv_forward_checking"):
            r = self.client.post(
                solve,
                {"grid": resp.json()["grid"], "algorithm": alg},
                content_type="application/json",
            )
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.json()["solved"])
