from __future__ import annotations

import html
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

from .fetch import download_file


@dataclass(frozen=True)
class TranscriptSource:
    path: str
    kind: str
    bytes: int
    url: str | None = None


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


TRANSCRIPT_URL_RE = re.compile(
    r"https?://[^\s\"'<>\\]+?\.(?:vtt|srt|txt)(?:\?[^\s\"'<>\\]*)?",
    re.IGNORECASE,
)


def _html_sources(out_dir: Path) -> list[Path]:
    return [
        path for path in [
            out_dir / "article.fragment.html",
            out_dir / "index.html",
            out_dir / "page.raw.html",
        ]
        if path.exists() and path.stat().st_size > 0
    ]


def _clean_url(url: str) -> str:
    # Substack often stores links in JSON/HTML escaped contexts.
    return html.unescape(unquote(url)).rstrip(".,);]")


def find_provided_transcript_urls(out_dir: Path) -> list[str]:
    """Return caption/transcript URLs embedded in exported Substack HTML, if any."""
    found: list[str] = []
    for source in _html_sources(out_dir):
        text = source.read_text(encoding="utf-8", errors="replace")
        for match in TRANSCRIPT_URL_RE.finditer(text):
            url = _clean_url(match.group(0))
            if url not in found:
                found.append(url)
    return found


def _provided_suffix(url: str) -> str:
    path = url.split("?", 1)[0].lower()
    for suffix in (".vtt", ".srt", ".txt"):
        if path.endswith(suffix):
            return suffix
    return ".txt"


def _strip_caption_markup(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip("\ufeff ")
        if not line or line.upper() == "WEBVTT" or line.isdigit():
            continue
        if "-->" in line:
            continue
        if line.startswith(("NOTE", "STYLE", "REGION")):
            continue
        lines.append(re.sub(r"<[^>]+>", "", line))
    return "\n".join(lines).strip() + "\n"


def download_provided_transcript(out_dir: Path, cookies: Path | None = None, force: bool = False) -> TranscriptSource | None:
    """Download a provider-supplied transcript/caption file before falling back to Whisper."""
    urls = find_provided_transcript_urls(out_dir)
    if not urls:
        return None

    trans_dir = out_dir / "transcript"
    trans_dir.mkdir(parents=True, exist_ok=True)
    url = urls[0]
    suffix = _provided_suffix(url)
    raw_rel = f"transcript/source_provided{suffix}"
    raw_path = out_dir / raw_rel
    size, _downloaded = download_file(url, raw_path, cookies_file=cookies, timeout=120, force=force)

    txt_rel = "transcript/source_provided.txt"
    txt_path = out_dir / txt_rel
    if suffix in {".vtt", ".srt"}:
        txt_path.write_text(_strip_caption_markup(raw_path.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
    elif raw_path != txt_path:
        txt_path.write_text(raw_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")

    if not txt_path.exists() or txt_path.stat().st_size == 0:
        return None
    return TranscriptSource(path=txt_rel, kind="provided_transcript", bytes=size, url=url)


def select_transcript_source(out_dir: Path) -> TranscriptSource | None:
    """Prefer provider transcript, then extracted audio, then extracted video."""
    provided = out_dir / "transcript" / "source_provided.txt"
    if provided.exists() and provided.stat().st_size > 0:
        return TranscriptSource(path=str(provided.relative_to(out_dir)), kind="provided_transcript", bytes=provided.stat().st_size)

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
    if source.kind == "provided_transcript":
        path = out_dir / source.path
        return path.exists() and path.stat().st_size > 0
    outputs = expected_outputs(source)
    required = [out_dir / outputs["txt"]]
    return all(path.exists() and path.stat().st_size > 0 for path in required)


def write_transcript_markdown(out_dir: Path, source: TranscriptSource, outputs: dict[str, str] | None, model: str, language: str) -> str:
    txt_path = out_dir / (source.path if source.kind == "provided_transcript" else outputs["txt"])
    md_path = out_dir / "transcript.md"
    engine = "Provider-supplied transcript/captions" if source.kind == "provided_transcript" else f"OpenAI Whisper CLI, model `{model}`"
    md_path.write_text(
        "# Transcript\n\n"
        f"- **Source:** `{source.path}`\n"
        f"- **Source kind:** `{source.kind}`\n"
        f"- **Transcription engine:** {engine}\n"
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


def _provided_outputs(source: TranscriptSource) -> dict[str, str]:
    return {"txt": source.path}


def transcribe(out_dir: Path, model: str = "small", language: str = "English", force: bool = False, cookies: Path | None = None) -> dict:
    provided_source = None if force else select_transcript_source(out_dir)
    if provided_source is None or provided_source.kind != "provided_transcript":
        provided_source = download_provided_transcript(out_dir, cookies=cookies, force=force)
    if provided_source is not None:
        outputs = _provided_outputs(provided_source)
        markdown = write_transcript_markdown(out_dir, provided_source, outputs, model, language)
        result = TranscriptResult(
            ok=True,
            source=provided_source.path,
            source_kind=provided_source.kind,
            text=provided_source.path,
            markdown=markdown,
            skipped_existing=not force,
            model=model,
            language=language,
            command=None,
            outputs=outputs,
        )
        write_manifest(out_dir, result)
        return result.to_dict()

    source = select_transcript_source(out_dir)
    if source is None:
        result = TranscriptResult(ok=False, error="No provided transcript, audio, or video source available for transcription", model=model, language=language)
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
