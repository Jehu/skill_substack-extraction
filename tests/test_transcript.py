import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from substack_extraction.transcript import expected_outputs, find_provided_transcript_urls, select_transcript_source, transcribe


class TranscriptTests(unittest.TestCase):
    def test_select_source_prefers_audio_over_video(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            audio = out / "media/audio/audio_01.mp3"
            video = out / "media/video/video_01.mp4"
            audio.parent.mkdir(parents=True)
            video.parent.mkdir(parents=True)
            audio.write_bytes(b"audio")
            video.write_bytes(b"video")
            source = select_transcript_source(out)
            self.assertIsNotNone(source)
            self.assertEqual(source.kind, "audio")
            self.assertEqual(source.path, "media/audio/audio_01.mp3")

    def test_select_source_falls_back_to_video(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            video = out / "media/video/video_01.mp4"
            video.parent.mkdir(parents=True)
            video.write_bytes(b"video")
            source = select_transcript_source(out)
            self.assertIsNotNone(source)
            self.assertEqual(source.kind, "video")

    def test_transcribe_skips_existing_and_writes_manifest_and_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            audio = out / "media/audio/audio_01.mp3"
            audio.parent.mkdir(parents=True)
            audio.write_bytes(b"audio")
            trans = out / "transcript"
            trans.mkdir()
            (trans / "audio_01.txt").write_text("Hello transcript", encoding="utf-8")
            with patch("substack_extraction.transcript.subprocess.run") as mocked:
                result = transcribe(out)
            mocked.assert_not_called()
            self.assertTrue(result["ok"])
            self.assertTrue(result["skipped_existing"])
            self.assertEqual(result["source_kind"], "audio")
            self.assertTrue((out / "transcript.md").exists())
            self.assertTrue((out / "transcript/manifest.json").exists())

    def test_transcribe_invokes_whisper_when_missing(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            audio = out / "media/audio/audio_01.mp3"
            audio.parent.mkdir(parents=True)
            audio.write_bytes(b"audio")

            def fake_run(cmd, check, stdout, stderr):
                outputs = expected_outputs(select_transcript_source(out))
                (out / outputs["txt"]).parent.mkdir(parents=True, exist_ok=True)
                (out / outputs["txt"]).write_text("Generated transcript", encoding="utf-8")
                return None

            with patch("substack_extraction.transcript.subprocess.run", side_effect=fake_run) as mocked:
                result = transcribe(out, model="tiny", language="English")
            mocked.assert_called_once()
            self.assertTrue(result["ok"])
            self.assertFalse(result["skipped_existing"])
            self.assertEqual(result["model"], "tiny")
            self.assertIn("Generated transcript", (out / "transcript.md").read_text(encoding="utf-8"))

    def test_transcribe_uses_provider_vtt_before_whisper(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / "article.fragment.html").write_text(
                '<track kind="captions" src="https://cdn.example.com/captions.vtt">',
                encoding="utf-8",
            )

            def fake_download(url, dest, cookies_file=None, timeout=300, force=False, min_bytes=1):
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text("WEBVTT\n\n00:00.000 --> 00:01.000\nHello from captions\n", encoding="utf-8")
                return dest.stat().st_size, True

            with patch("substack_extraction.transcript.download_file", side_effect=fake_download) as downloaded, \
                 patch("substack_extraction.transcript.subprocess.run") as whispered:
                result = transcribe(out)

            downloaded.assert_called_once()
            whispered.assert_not_called()
            self.assertTrue(result["ok"])
            self.assertEqual(result["source_kind"], "provided_transcript")
            self.assertIn("Hello from captions", (out / "transcript.md").read_text(encoding="utf-8"))

    def test_find_provided_transcript_urls_unescapes_html(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / "index.html").write_text(
                'src="https://cdn.example.com/a%20caption.vtt?token=abc&amp;x=1"',
                encoding="utf-8",
            )
            self.assertEqual(
                find_provided_transcript_urls(out),
                ["https://cdn.example.com/a caption.vtt?token=abc&x=1"],
            )

    def test_transcribe_missing_source_returns_manifest_error(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            result = transcribe(out)
            self.assertFalse(result["ok"])
            self.assertTrue((out / "transcript/manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
