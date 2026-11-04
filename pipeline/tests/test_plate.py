"""Run with: python -m unittest discover -s pipeline/tests -v"""
import base64
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reel import muse_image, plate


class PlateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name) / "cache"
        self.ledger = Path(self.temp.name) / "spend.log"
        for module in (plate, muse_image):
            self.enterContext(patch.object(module, "CACHE", str(self.cache)))
        self.enterContext(patch.object(muse_image, "LEDGER", str(self.ledger)))
        self.enterContext(patch.dict(os.environ, {"META_MODEL_API_KEY": "test-key"}, clear=True))
        raw = io.BytesIO()
        Image.new("RGB", (48, 32), "blue").save(raw, "PNG")
        self.response = json.dumps({"data": [{"b64_json": base64.b64encode(raw.getvalue()).decode()}]}).encode()

    def test_direct_meta_upload_preserves_crop_size_and_reuses_cache(self):
        crop = Image.new("RGB", (40, 80), "red")
        with patch.object(muse_image.urllib.request, "urlopen", return_value=io.BytesIO(self.response)) as api:
            result = plate.plate(crop, "first")
            again = plate.plate(crop, "rerun")
        self.assertEqual(result.size, crop.size)
        self.assertEqual(result.mode, "RGB")
        self.assertEqual(result.getpixel((0, 0)), (0, 0, 255))
        self.assertEqual(again.tobytes(), result.tobytes())
        api.assert_called_once()
        request = api.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.meta.ai/v1/images/edits")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertIn(b"muse-image-1.0", request.data)
        self.assertIn(b"40x80", request.data)
        self.assertIn(b'name="image[0]"', request.data)
        raw = io.BytesIO()
        crop.save(raw, "PNG")
        self.assertIn(raw.getvalue(), request.data)
        lines = self.ledger.read_text().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("\tmuse-image\tfirst\t$0.0100\t", lines[0])

    def test_changed_crop_or_prompt_gets_a_new_request(self):
        with patch.object(muse_image.urllib.request, "urlopen", side_effect=lambda *a, **k: io.BytesIO(self.response)) as api:
            crop = Image.new("RGB", (80, 40), "red")
            plate.plate(crop, "original")
            plate.plate(crop, "new prompt", prompt=plate.PROMPT + " Preserve lettering.")
            plate.plate(Image.new("RGB", crop.size, "green"), "new crop")
        self.assertEqual(api.call_count, 3)
        self.assertEqual(len(self.ledger.read_text().splitlines()), 3)

    def test_http_failure_is_not_cached(self):
        error = HTTPError("https://api.meta.ai/v1/images/edits", 403, "Forbidden", {}, io.BytesIO(b"denied"))
        self.addCleanup(error.close)
        with patch.object(muse_image.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(HTTPError):
                plate.plate(Image.new("RGB", (40, 40)), "failure")
        self.assertEqual(list(self.cache.glob("muse-image-*.json")), [])

    def test_text_only_prompt_uses_generation_endpoint_and_cache(self):
        with patch.object(muse_image.urllib.request, "urlopen", return_value=io.BytesIO(self.response)) as api:
            muse_image.paint("Paint the selected moment", [], label="moment")
            muse_image.paint("Paint the selected moment", [], label="rerun")
        api.assert_called_once()
        request = api.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.meta.ai/v1/images/generations")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        body = json.loads(request.data)
        self.assertEqual(body["model"], "muse-image-1.0")
        self.assertEqual(body["prompt"], "Paint the selected moment")
        self.assertEqual(len(self.ledger.read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
