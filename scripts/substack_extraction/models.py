from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExtractOptions:
    url: str
    cookies: Path
    output_root: Path
    include_media: bool = False
    transcribe: bool = False
    follow: list[str] = field(default_factory=list)
    follow_domain: list[str] = field(default_factory=list)
    debug: bool = False
    force: bool = False


@dataclass
class DownloadedFile:
    path: Path
    url: str
    bytes: int
    ok: bool
    error: str | None = None
