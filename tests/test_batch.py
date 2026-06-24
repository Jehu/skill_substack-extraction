import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from substack_extraction.cli import batch_options_from_config, run_batch


class BatchTests(unittest.TestCase):
    def test_batch_options_from_config_accepts_global_and_per_url_overrides(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "batch.json"
            cfg.write_text(json.dumps({
                "cookies": "/cookies.txt",
                "output_root": "/exports",
                "follow": ["Grab the Prompts"],
                "follow_domain": ["promptkit.natebjones.com"],
                "urls": [
                    "https://example.com/p/one",
                    {"url": "https://example.com/p/two", "transcribe": True, "follow": ["Other"]},
                ],
            }), encoding="utf-8")
            options, _ = batch_options_from_config(cfg)
            self.assertEqual(len(options), 2)
            self.assertEqual(options[0].follow, ["Grab the Prompts"])
            self.assertFalse(options[0].transcribe)
            self.assertTrue(options[1].transcribe)
            self.assertEqual(options[1].follow, ["Other"])

    def test_run_batch_writes_manifest_and_continues(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "exports"
            cfg = Path(td) / "batch.json"
            cfg.write_text(json.dumps({
                "cookies": "/cookies.txt",
                "output_root": str(root),
                "urls": ["https://example.com/p/ok", "https://example.com/p/fail"],
            }), encoding="utf-8")

            def fake_extract(options):
                if options.url.endswith("fail"):
                    raise RuntimeError("boom")
                out = root / "example" / "ok"
                out.mkdir(parents=True)
                return out

            with patch("substack_extraction.cli.extract", side_effect=fake_extract):
                manifest = run_batch(cfg, continue_on_error=True)
            self.assertEqual(manifest["total"], 2)
            self.assertEqual(manifest["completed"], 2)
            self.assertEqual(manifest["ok_count"], 1)
            self.assertEqual(manifest["error_count"], 1)
            self.assertTrue((root / "batch_manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
