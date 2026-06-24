from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


@dataclass
class ParsedPost:
    preloads: dict
    post: dict
    publication_host: str

    @property
    def title(self) -> str:
        return self.post.get("title") or "untitled"

    @property
    def slug(self) -> str:
        return self.post.get("slug") or urlparse(self.post.get("canonical_url", "")).path.rstrip("/").split("/")[-1]

    @property
    def published_date(self) -> str:
        raw = self.post.get("post_date") or self.post.get("published_at") or ""
        return raw[:10] if raw else datetime.now().date().isoformat()

    @property
    def output_publication_slug(self) -> str:
        host = self.publication_host.split(":", 1)[0]
        return host.split(".")[0] if host else "substack"


def _decode_json_parse_arg(raw: str) -> dict:
    decoded = json.loads('"' + raw + '"')
    return json.loads(decoded)


def extract_preloads(html: str) -> dict:
    match = re.search(r"window\._preloads\s*=\s*JSON\.parse\(\"(.*?)\"\)", html, re.S)
    if not match:
        raise ValueError("Substack preload JSON not found in HTML")
    return _decode_json_parse_arg(match.group(1))


def parse_post(html: str, source_url: str) -> ParsedPost:
    preloads = extract_preloads(html)
    post = preloads.get("post")
    if not isinstance(post, dict):
        raise ValueError("Substack preload JSON did not contain a post object")
    host = urlparse(post.get("canonical_url") or source_url).netloc
    return ParsedPost(preloads=preloads, post=post, publication_host=host)


def safe_filename(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-._")
    return value or "item"


def output_dir_for(parsed: ParsedPost, output_root: Path) -> Path:
    return output_root / parsed.output_publication_slug / f"{parsed.published_date}_{safe_filename(parsed.slug)}"
