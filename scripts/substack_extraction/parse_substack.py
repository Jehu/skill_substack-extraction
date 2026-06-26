from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse


class AccessRequiredError(ValueError):
    """Raised when the fetched page is an access/login gate instead of a post."""


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


ACCESS_REQUIRED_HINTS = (
    "sign in",
    "log in",
    "login",
    "subscribe to continue",
    "subscribe to read",
    "become a paid subscriber",
    "only available to paid subscribers",
    "this post is for paid subscribers",
    "continue reading",
    "enable cookies",
    "cookies are required",
    "cookie consent",
    "captcha",
)


def looks_like_access_required(html: str, source_url: str = "") -> bool:
    """Return True for obvious login/cookie/paywall gate pages.

    Authorized exports need Substack's preload JSON for the actual post. When it
    is absent and the page contains access-gate wording, continuing would create
    misleading artifacts from the gate page rather than the article.
    """
    url_path = urlparse(source_url).path.lower()
    if any(part in url_path for part in ("/sign-in", "/signin", "/login", "/account")):
        return True

    text = re.sub(r"<[^>]+>", " ", html).lower()
    text = re.sub(r"\s+", " ", text)
    return any(hint in text for hint in ACCESS_REQUIRED_HINTS)


def parse_post(html: str, source_url: str) -> ParsedPost:
    try:
        preloads = extract_preloads(html)
    except ValueError as exc:
        if looks_like_access_required(html, source_url):
            raise AccessRequiredError(
                "Login/cookies required: the fetched page looks like an access gate, "
                "not the Substack post. Re-export fresh authorized cookies for this "
                "publication/account and retry. No article content was extracted."
            ) from exc
        raise
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
