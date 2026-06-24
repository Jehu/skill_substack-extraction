import json
import tempfile
import unittest
from pathlib import Path

from substack_extraction.verify import verify_export, write_run_manifest, write_verify_report


class VerifyTests(unittest.TestCase):
    def test_verify_minimal_export_ok_and_writes_reports(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / "media").mkdir()
            (out / "index.md").write_text("---\n---\nBody", encoding="utf-8")
            (out / "index.html").write_text("<p>Body</p>", encoding="utf-8")
            (out / "article.fragment.html").write_text("<p>Body</p>", encoding="utf-8")
            (out / "metadata.json").write_text(json.dumps({"markdown_validation": {"ok": True}}), encoding="utf-8")
            for name in ["image_urls.txt", "audio_urls.txt", "video_urls.txt"]:
                (out / "media" / name).write_text("", encoding="utf-8")
            verification = verify_export(out)
            self.assertTrue(verification["ok"])
            write_verify_report(out, verification)
            write_run_manifest(out, {"title": "T"}, verification)
            self.assertTrue((out / "verification_report.md").exists())
            self.assertTrue((out / "run_manifest.json").exists())

    def test_verify_catches_forbidden_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / "media").mkdir()
            (out / "index.md").write_text("subscription-widget", encoding="utf-8")
            (out / "index.html").write_text("x", encoding="utf-8")
            (out / "article.fragment.html").write_text("x", encoding="utf-8")
            (out / "metadata.json").write_text(json.dumps({"markdown_validation": {"ok": True}}), encoding="utf-8")
            for name in ["image_urls.txt", "audio_urls.txt", "video_urls.txt"]:
                (out / "media" / name).write_text("", encoding="utf-8")
            verification = verify_export(out)
            self.assertFalse(verification["ok"])
            self.assertGreaterEqual(verification["error_count"], 1)
