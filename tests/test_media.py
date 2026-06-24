import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from substack_extraction.media import (
    build_media_plan,
    collect_media_urls,
    download_media,
    infer_image_extension,
)


class MediaTests(unittest.TestCase):
    def test_collect_media_urls_and_plan_are_deterministic(self):
        post = {
            "body_html": '<p><img src="https://cdn.example.com/a.webp"></p><p><img src="https://cdn.example.com/a.webp"></p>',
            "cover_image": "https://cdn.example.com/cover.jpeg",
            "podcast_url": "https://audio.example.com/episode.mp3",
            "videoUpload": {"id": "vid123", "mux_playback_id": "muxabc"},
        }
        urls = collect_media_urls(post, "pub.substack.com")
        self.assertEqual(urls["images"], ["https://cdn.example.com/cover.jpeg", "https://cdn.example.com/a.webp"])
        self.assertEqual(urls["audio"], ["https://audio.example.com/episode.mp3"])
        self.assertEqual(urls["video"][0], "https://pub.substack.com/api/v1/video/upload/vid123/src")
        self.assertEqual(urls["video"][1], "https://stream.mux.com/muxabc.m3u8")
        plan = build_media_plan(urls)
        self.assertEqual([item.path for item in plan[:3]], [
            "media/images/image_01.jpeg",
            "media/images/image_02.webp",
            "media/audio/audio_01.mp3",
        ])
        self.assertEqual(plan[3].strategy, "substack-video-src")
        self.assertEqual(plan[4].strategy, "mux-hls-candidate")

    def test_infer_image_extension_defaults_safely(self):
        self.assertEqual(infer_image_extension("https://substackcdn.com/image/fetch/abc"), "jpg")
        self.assertEqual(infer_image_extension("https://x/y.png?width=10"), "png")

    def test_download_media_writes_plan_results_and_skips_existing(self):
        urls = {"images": ["https://example.com/i.jpg"], "audio": [], "video": []}
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            dest = out / "media/images/image_01.jpg"
            dest.parent.mkdir(parents=True)
            dest.write_bytes(b"existing")
            results = download_media(out, Path("/tmp/no-cookies.txt"), urls)
            self.assertTrue((out / "media/download_plan.json").exists())
            self.assertTrue((out / "media/download_results.json").exists())
            self.assertTrue(results["images"][0]["ok"])
            self.assertTrue(results["images"][0]["skipped_existing"])
            self.assertEqual(results["images"][0]["bytes"], len(b"existing"))

    def test_download_media_downloads_missing_file_via_fetch_layer(self):
        urls = {"images": ["https://example.com/i.jpg"], "audio": [], "video": []}
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            with patch("substack_extraction.fetch.fetch_url", return_value=(b"new-data", {}, "https://example.com/i.jpg")):
                # Patch the symbol used by media.py's imported download_file indirectly by patching underlying fetch_url module symbol is not enough.
                pass
            with patch("substack_extraction.media.download_file", return_value=(8, True)) as mocked:
                results = download_media(out, Path("/tmp/no-cookies.txt"), urls)
            mocked.assert_called_once()
            self.assertTrue(results["images"][0]["ok"])
            self.assertFalse(results["images"][0]["skipped_existing"])
            self.assertEqual(results["images"][0]["bytes"], 8)


if __name__ == "__main__":
    unittest.main()
