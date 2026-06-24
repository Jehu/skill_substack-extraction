import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from substack_extraction.transcript import expected_outputs, select_transcript_source, transcribe


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

    def test_transcribe_missing_source_returns_manifest_error(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            result = transcribe(out)
            self.assertFalse(result["ok"])
            self.assertTrue((out / "transcript/manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
