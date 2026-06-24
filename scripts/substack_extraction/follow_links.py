from __future__ import annotations

import json
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .fetch import fetch_url
from .parse_substack import safe_filename


@dataclass(frozen=True)
class LinkCandidate:
    label: str
    url: str
    matched_by: list[str]


@dataclass
class FollowResult:
    ok: bool
    label: str
    url: str
    final_url: str | None = None
    path: str | None = None
    bytes: int = 0
    source_markdown: str | None = None
    strategy: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def discover_links(body_html: str, text_patterns: list[str], domains: list[str], base_url: str | None = None) -> list[tuple[str, str]]:
    """Backward-compatible public API returning (label, url)."""
    return [(c.label, c.url) for c in discover_link_candidates(body_html, text_patterns, domains, base_url)]


def discover_link_candidates(
    body_html: str,
    text_patterns: list[str],
    domains: list[str],
    base_url: str | None = None,
) -> list[LinkCandidate]:
    soup = BeautifulSoup(body_html, "html.parser")
    found: list[LinkCandidate] = []
    normalized_domains = [d.lower().strip() for d in domains if d.strip()]
    normalized_patterns = [p.lower().strip() for p in text_patterns if p.strip()]
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url or "", a["href"])
        label = re.sub(r"\s+", " ", a.get_text(" ", strip=True)) or href
        host = urlparse(href).netloc.lower()
        matched_by: list[str] = []
        if any(pattern in label.lower() for pattern in normalized_patterns):
            matched_by.append("text")
        if any(host == d or host.endswith("." + d) for d in normalized_domains):
            matched_by.append("domain")
        if matched_by:
            found.append(LinkCandidate(label=label, url=href, matched_by=matched_by))

    deduped: list[LinkCandidate] = []
    seen: set[str] = set()
    for candidate in found:
        key = normalize_url_for_dedupe(candidate.url)
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def normalize_url_for_dedupe(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


def promptkit_markdown_endpoint(url: str) -> str | None:
    path = urlparse(url).path.strip("/")
    if not path:
        return None
    asset_id = path.split("/")[-1]
    if not asset_id:
        return None
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/api/assets/{asset_id}/markdown"


def follow_link(label: str, url: str, parent_url: str, dest_dir: Path, index: int) -> dict:
    """Backward-compatible single-link API."""
    return follow_candidate(LinkCandidate(label, url, ["manual"]), parent_url, dest_dir, index).to_dict()


def follow_candidate(candidate: LinkCandidate, parent_url: str, dest_dir: Path, index: int) -> FollowResult:
    slug = safe_filename(candidate.label)[:40] or safe_filename(urlparse(candidate.url).path.rsplit("/", 1)[-1])
    link_dir = dest_dir / "linked" / f"{index:02d}_{slug}"
    link_dir.mkdir(parents=True, exist_ok=True)
    try:
        raw, _headers, final_url = fetch_url(candidate.url)
        (link_dir / "page.raw.html").write_bytes(raw)
        md_body, source_md, strategy = render_link_markdown(raw, final_url, link_dir)
        title = html_title(raw.decode("utf-8", errors="replace")) or candidate.label
        front = ["---", f'title: "{yaml_escape(title)}"', f'source: "{candidate.url}"']
        if final_url != candidate.url:
            front.append(f'final_url: "{final_url}"')
        if source_md:
            front.append(f'source_markdown: "{source_md}"')
        front += [f'parent: "{parent_url}"', f'strategy: "{strategy}"', "---", ""]
        index_path = link_dir / "index.md"
        index_path.write_text("\n".join(front) + "\n" + md_body.strip() + "\n", encoding="utf-8")
        return FollowResult(
            ok=True,
            label=candidate.label,
            url=candidate.url,
            final_url=final_url,
            path=str(index_path.relative_to(dest_dir)),
            bytes=index_path.stat().st_size,
            source_markdown=source_md,
            strategy=strategy,
        )
    except Exception as e:
        return FollowResult(ok=False, label=candidate.label, url=candidate.url, error=str(e))


def follow_links_stage(
    body_html: str,
    text_patterns: list[str],
    domains: list[str],
    parent_url: str,
    dest_dir: Path,
) -> list[dict]:
    linked_dir = dest_dir / "linked"
    linked_dir.mkdir(parents=True, exist_ok=True)
    candidates = discover_link_candidates(body_html, text_patterns, domains, parent_url)
    results = [follow_candidate(candidate, parent_url, dest_dir, i).to_dict() for i, candidate in enumerate(candidates)]
    manifest = {
        "parent_url": parent_url,
        "text_patterns": text_patterns,
        "domains": domains,
        "candidate_count": len(candidates),
        "candidates": [asdict(c) for c in candidates],
        "results": results,
    }
    (linked_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return results


def render_link_markdown(raw_html: bytes, final_url: str, link_dir: Path) -> tuple[str, str | None, str]:
    source_md = None
    md_body = None
    strategy = "html-fallback"
    if "promptkit" in urlparse(final_url).netloc.lower():
        endpoint = promptkit_markdown_endpoint(final_url)
        if endpoint:
            try:
                md_raw, _mh, _mf = fetch_url(endpoint)
                text = md_raw.decode("utf-8", errors="replace")
                if looks_like_markdown_asset(text):
                    (link_dir / "native_markdown.raw.md").write_text(text, encoding="utf-8")
                    md_body = strip_frontmatter(text)
                    source_md = endpoint
                    strategy = "native-markdown"
            except Exception:
                md_body = None
    if md_body is None:
        md_body = html_to_markdown_fallback(raw_html)
    return md_body, source_md, strategy


def looks_like_markdown_asset(text: str) -> bool:
    return len(text.strip()) > 20 and ("Prompt" in text or "#" in text or "```" in text)


def html_to_markdown_fallback(raw_html: bytes) -> str:
    try:
        proc = subprocess.run(["pandoc", "-f", "html", "-t", "gfm", "--wrap=none"], input=raw_html, capture_output=True, check=True)
        text = proc.stdout.decode("utf-8", errors="replace")
        if text.strip():
            return text
    except Exception:
        pass
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n", strip=True)


def strip_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, min(len(lines), 80)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :]).lstrip()
    return text


def html_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    return soup.title.string.strip() if soup.title and soup.title.string else None


def yaml_escape(value: str) -> str:
    return value.replace('"', '\\"')
