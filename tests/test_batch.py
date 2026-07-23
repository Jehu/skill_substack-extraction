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



    def test_batch_cookies_can_come_from_env(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "batch.json"
            cfg.write_text(json.dumps({
                "output_root": "/exports",
                "urls": ["https://example.com/p/one"],
            }), encoding="utf-8")
            with patch.dict("os.environ", {"SUBSTACK_COOKIES": "/env/cookies.txt"}, clear=False):
                options, _ = batch_options_from_config(cfg)
            self.assertEqual(str(options[0].cookies), "/env/cookies.txt")

    def test_batch_per_url_cookies_override_env(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "batch.json"
            cfg.write_text(json.dumps({
                "output_root": "/exports",
                "urls": [{"url": "https://example.com/p/one", "cookies": "/item/cookies.txt"}],
            }), encoding="utf-8")
            with patch.dict("os.environ", {"SUBSTACK_COOKIES": "/env/cookies.txt"}, clear=False):
                options, _ = batch_options_from_config(cfg)
            self.assertEqual(str(options[0].cookies), "/item/cookies.txt")

    def test_batch_output_root_can_come_from_env(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "batch.json"
            cfg.write_text(json.dumps({
                "cookies": "/cookies.txt",
                "urls": ["https://example.com/p/one"],
            }), encoding="utf-8")
            with patch.dict("os.environ", {"SUBSTACK_EXPORT_ROOT": "/env/exports"}, clear=False):
                options, _ = batch_options_from_config(cfg)
            self.assertEqual(str(options[0].output_root), "/env/exports")

    def test_batch_per_url_output_root_overrides_env(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "batch.json"
            cfg.write_text(json.dumps({
                "cookies": "/cookies.txt",
                "urls": [{"url": "https://example.com/p/one", "output_root": "/item/exports"}],
            }), encoding="utf-8")
            with patch.dict("os.environ", {"SUBSTACK_EXPORT_ROOT": "/env/exports"}, clear=False):
                options, _ = batch_options_from_config(cfg)
            self.assertEqual(str(options[0].output_root), "/item/exports")

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
