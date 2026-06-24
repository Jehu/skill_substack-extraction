from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class TranscriptSource:
    path: str
    kind: str
    bytes: int


@dataclass
class TranscriptResult:
    ok: bool
    source: str | None = None
    source_kind: str | None = None
    text: str | None = None
    markdown: str | None = None
    manifest: str = "transcript/manifest.json"
    skipped_existing: bool = False
    model: str = "small"
    language: str = "English"
    command: list[str] | None = None
    outputs: dict[str, str] | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def select_transcript_source(out_dir: Path) -> TranscriptSource | None:
    """Prefer extracted audio, fallback to extracted video."""
    candidates = [
        ("audio", out_dir / "media" / "audio" / "audio_01.mp3"),
        ("video", out_dir / "media" / "video" / "video_01.mp4"),
    ]
    for kind, path in candidates:
        if path.exists() and path.stat().st_size > 0:
            return TranscriptSource(path=str(path.relative_to(out_dir)), kind=kind, bytes=path.stat().st_size)
    return None


def expected_outputs(source: TranscriptSource) -> dict[str, str]:
    stem = Path(source.path).stem
    return {
        "txt": f"transcript/{stem}.txt",
        "srt": f"transcript/{stem}.srt",
        "vtt": f"transcript/{stem}.vtt",
        "tsv": f"transcript/{stem}.tsv",
        "json": f"transcript/{stem}.json",
    }


def transcript_complete(out_dir: Path, source: TranscriptSource) -> bool:
    outputs = expected_outputs(source)
    required = [out_dir / outputs["txt"]]
    return all(path.exists() and path.stat().st_size > 0 for path in required)


def write_transcript_markdown(out_dir: Path, source: TranscriptSource, outputs: dict[str, str], model: str, language: str) -> str:
    txt_path = out_dir / outputs["txt"]
    md_path = out_dir / "transcript.md"
    md_path.write_text(
        "# Transcript\n\n"
        f"- **Source:** `{source.path}`\n"
        f"- **Source kind:** `{source.kind}`\n"
        f"- **Transcription engine:** OpenAI Whisper CLI, model `{model}`\n"
        f"- **Language:** {language}\n"
        f"- **Generated:** `{datetime.now().isoformat(timespec='seconds')}`\n\n"
        "## Transcript\n\n" + txt_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    return "transcript.md"


def write_manifest(out_dir: Path, result: TranscriptResult) -> None:
    manifest = out_dir / result.manifest
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")


def transcribe(out_dir: Path, model: str = "small", language: str = "English", force: bool = False) -> dict:
    source = select_transcript_source(out_dir)
    if source is None:
        result = TranscriptResult(ok=False, error="No audio or video source available for transcription", model=model, language=language)
        write_manifest(out_dir, result)
        return result.to_dict()

    trans_dir = out_dir / "transcript"
    trans_dir.mkdir(parents=True, exist_ok=True)
    outputs = expected_outputs(source)
    cmd = [
        "whisper", str(out_dir / source.path), "--language", language, "--task", "transcribe",
        "--model", model, "--output_dir", str(trans_dir), "--output_format", "all", "--verbose", "False",
    ]
    log = trans_dir / "whisper.log"

    if force or not transcript_complete(out_dir, source):
        try:
            with log.open("w", encoding="utf-8") as fh:
                subprocess.run(cmd, check=True, stdout=fh, stderr=subprocess.STDOUT)
        except Exception as e:
            result = TranscriptResult(
                ok=False, source=source.path, source_kind=source.kind, model=model, language=language,
                command=cmd, outputs=outputs, error=str(e),
            )
            write_manifest(out_dir, result)
            return result.to_dict()
        skipped = False
    else:
        skipped = True

    if not transcript_complete(out_dir, source):
        result = TranscriptResult(
            ok=False, source=source.path, source_kind=source.kind, model=model, language=language,
            command=cmd, outputs=outputs, error="Whisper completed but transcript text file was not found",
        )
        write_manifest(out_dir, result)
        return result.to_dict()

    markdown = write_transcript_markdown(out_dir, source, outputs, model, language)
    result = TranscriptResult(
        ok=True,
        source=source.path,
        source_kind=source.kind,
        text=outputs["txt"],
        markdown=markdown,
        skipped_existing=skipped,
        model=model,
        language=language,
        command=cmd,
        outputs=outputs,
    )
    write_manifest(out_dir, result)
    return result.to_dict()
