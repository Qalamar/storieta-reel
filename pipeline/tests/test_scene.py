import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reel import scene


class SceneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / "output"
        self.image = Image.new("RGB", (64, 48), "blue")
        self.moment = {"sentence": "The lamps were lit.", "shot": "Holmes waits beneath a lamp at dusk.",
                       "characters": ["Sherlock Holmes"]}
        self.calls = Mock()
        for name, value in (("read", self.moment), ("paint", self.image), ("segment", "masks"),
                            ("direct", ({"figures": []}, {})), ("plate", self.image)):
            mock = self.enterContext(patch.object(scene, name, return_value=value))
            self.calls.attach_mock(mock, name)
        self.instances = self.enterContext(patch.object(scene, "instances", return_value=[]))
        self.marked_page = scene.layers.marked_page
        self.marker = self.enterContext(patch.object(scene.layers, "marked_page", return_value=self.image))

    def run_brief(self, brief):
        path = self.root / "brief.json"
        path.write_text(json.dumps(brief))
        scene.main(str(self.out), str(path))

    def test_selected_moment_is_painted_before_masks_and_casting(self):
        (self.root / "passage.txt").write_text("A passage to illustrate.")
        self.run_brief({"book": "Sherlock", "passage": "passage.txt", "prompt": "Watercolor.",
                        "size": "1024x1536", "shot": "Old shot", "characters": ["Old cast"]})
        self.assertEqual([call[0] for call in self.calls.mock_calls], ["read", "paint", "segment", "direct", "plate"])
        self.calls.read.assert_called_once_with("Sherlock", "A passage to illustrate.", "output read")
        prompt, refs, size, _ = self.calls.paint.call_args.args
        self.assertIn(self.moment["sentence"], prompt)
        self.assertIn(self.moment["shot"], prompt)
        self.assertIn("Sherlock Holmes", prompt)
        self.assertIn("Watercolor.", prompt)
        self.assertNotIn("Old shot", prompt)
        self.assertEqual(refs, [])
        self.assertEqual(size, "1024x1536")
        self.assertEqual(self.calls.direct.call_args.args[1], self.moment["shot"])
        self.assertEqual(self.calls.direct.call_args.args[2], self.moment["characters"])
        self.assertEqual(json.loads((self.out / "reading.json").read_text()), self.moment)
        self.assertTrue((self.out / "room.png").exists())

    def test_passage_does_not_require_a_handwritten_prompt(self):
        (self.root / "passage.txt").write_text("A passage.")
        self.run_brief({"passage": "passage.txt"})
        self.assertIn(self.moment["shot"], self.calls.paint.call_args.args[0])

    def test_prompt_only_brief_still_works(self):
        self.run_brief({"prompt": "A quiet street."})
        self.calls.read.assert_not_called()
        self.calls.paint.assert_called_once_with("A quiet street.", [], "1536x1024", "output")

    def test_existing_image_skips_scene_generation(self):
        self.image.save(self.root / "existing.png")
        self.run_brief({"image": "existing.png"})
        self.calls.read.assert_not_called()
        self.calls.paint.assert_not_called()
        self.calls.plate.assert_called_once()

    def test_named_figure_exports_transparency_and_filled_background(self):
        mask = np.zeros((48, 64), dtype=bool)
        mask[10:30, 20:35] = True
        self.instances.return_value = [(0.9, mask)]
        self.marker.side_effect = self.marked_page
        self.calls.direct.return_value = ({"figures": [{"mark": 1, "name": "Holmes"}]}, {})
        self.calls.plate.return_value = Image.new("RGB", self.image.size, "red")
        self.run_brief({"prompt": "Holmes on a street.", "characters": ["Holmes"]})
        with Image.open(self.out / "cast-1.png") as cast:
            self.assertEqual(cast.mode, "RGBA")
            self.assertEqual(cast.getpixel((25, 20))[3], 255)
            self.assertEqual(cast.getpixel((0, 0))[3], 0)
        with Image.open(self.out / "room.png") as room:
            self.assertEqual(room.getpixel((25, 20)), (255, 0, 0))
            self.assertEqual(room.getpixel((0, 0)), (0, 0, 255))
        self.assertTrue((self.out / "marked.jpg").is_file())
        manifest = json.loads((self.out / "reel.json").read_text())
        self.assertEqual(manifest["version"], 1)
        playable = manifest["scenes"][0]
        self.assertEqual(playable["layers"], [{"name": "Holmes", "src": "cast-1.png"}])
        for name in (playable["image"], playable["background"], playable["marked"], playable["layers"][0]["src"]):
            self.assertTrue((self.out / name).is_file())

    def test_invalid_casting_stops_after_one_corrective_turn(self):
        self.calls.direct.return_value = ({"figures": [{"mark": 99, "name": "Unknown"}]}, {})
        with self.assertRaisesRegex(RuntimeError, "Unknown mark: 99"):
            self.run_brief({"prompt": "A street."})
        self.assertEqual(self.calls.direct.call_count, 2)
        self.calls.plate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
