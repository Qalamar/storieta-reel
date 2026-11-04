import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reel.playlist import combine


class PlaylistTests(unittest.TestCase):
    def test_combines_scenes_and_rebases_asset_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = []
            for name in ("one", "two"):
                folder = root / name
                folder.mkdir()
                for filename in ("scene.png", "room.png", "cast.png"):
                    (folder / filename).touch()
                manifest = folder / "reel.json"
                manifest.write_text(json.dumps({"version": 1, "provenance": name, "scenes": [{
                    "image": "scene.png", "background": "room.png", "layers": [{"name": "Hero", "src": "cast.png"}]}]}))
                sources.append(manifest)
            output = root / "collection" / "reel.json"
            combine(output, sources)
            result = json.loads(output.read_text())
            self.assertEqual(len(result["scenes"]), 2)
            self.assertIn("one", result["provenance"])
            self.assertIn("two", result["provenance"])
            for i, scene in enumerate(result["scenes"]):
                for path in (scene["image"], scene["background"], scene["layers"][0]["src"]):
                    self.assertTrue((output.parent / path).is_file())
                self.assertEqual((output.parent / scene["image"]).resolve().parent, sources[i].parent.resolve())

    def test_missing_assets_fail_before_writing_playlist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "reel.json"
            source.write_text(json.dumps({"version": 1, "scenes": [{"image": "missing.png", "layers": []}]}))
            with self.assertRaises(FileNotFoundError):
                combine(root / "output.json", [source])
            self.assertFalse((root / "output.json").exists())
