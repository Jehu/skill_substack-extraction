from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag

DEFAULT_REQUIRED_PHRASES = [
    "Here’s what’s inside",
    "The work around the prompt",
    "Why apps made this worse",
    "When loops start noticing each other",
    "The Mary Poppins version",
    "What to notice first",
    "Coming Up",
    "Related Reading",
]
FORBIDDEN_MARKDOWN_PHRASES = [
    "subscription-widget",
    "SubscribeWidgetToDOM",
    "data:image/svg",
    "tags:\n  - \"clippings\"",
]


@dataclass(frozen=True)
class MarkdownValidation:
    ok: bool
    missing_required: list[str]
    present_forbidden: list[str]
    image_count: int
    heading_count: int


def html_document(title: str, subtitle: str, body_html: str) -> str:
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html_lib.escape(title)}</title>
</head>
<body>
  <h1>{html_lib.escape(title)}</h1>
  <p><em>{html_lib.escape(subtitle or '')}</em></p>
  {body_html}
</body>
</html>
'''


def _inline_md(node) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    name = node.name.lower()
    if name in {"strong", "b"}:
        t = "".join(_inline_md(c) for c in node.children).strip()
        return f"**{t}**" if t else ""
    if name in {"em", "i"}:
        t = "".join(_inline_md(c) for c in node.children).strip()
        return f"*{t}*" if t else ""
    if name == "a":
        label = "".join(_inline_md(c) for c in node.children).strip() or node.get("href", "")
        href = node.get("href", "")
        return f"[{label}]({href})" if href else label
    if name == "br":
        return "\n"
    if name == "img":
        src = node.get("src") or node.get("data-src") or ""
        alt = node.get("alt") or node.get("title") or ""
        return f"![{alt}]({src})" if src and not src.startswith("data:image") else ""
    if name == "code":
        t = "".join(_inline_md(c) for c in node.children).strip()
        return f"`{t}`" if t else ""
    return "".join(_inline_md(c) for c in node.children)


def _clean_inline(text: str) -> str:
    text = html_lib.unescape(text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def _remove_non_content(soup: BeautifulSoup) -> None:
    for selector in [
        ".subscription-widget-wrap-editor", ".subscription-widget",
        '[component-name="SubscribeWidgetToDOM"]', '[data-component-name="SubscribeWidgetToDOM"]',
        ".image-link-expand", "button", "script", "style", "iframe",
    ]:
        for tag in soup.select(selector):
            tag.decompose()
    for img in list(soup.find_all("img")):
        if (img.get("src") or "").startswith("data:image/svg"):
            img.decompose()


def body_html_to_markdown(body_html: str) -> str:
    """Convert Substack body_html to deterministic, archive-friendly Markdown."""
    soup = BeautifulSoup(body_html, "html.parser")
    _remove_non_content(soup)
    blocks: list[str] = []

    def add_block(value: str) -> None:
        value = _clean_inline(value)
        if value and value != "Subscribe" and "I make this Substack thanks to readers like you!" not in value:
            blocks.append(value)

    for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "ul", "ol", "figure"], recursive=True):
        if el.find_parent(["p", "ul", "ol", "figure"]) and el.name != "figure":
            continue
        if el.name in {"h1", "h2", "h3", "h4"}:
            add_block("#" * int(el.name[1]) + " " + _clean_inline(_inline_md(el)))
        elif el.name == "p":
            add_block(_inline_md(el))
        elif el.name in {"ul", "ol"}:
            lines = []
            for li in el.find_all("li", recursive=False):
                s = _clean_inline(_inline_md(li))
                if s:
                    lines.append("- " + s)
            add_block("\n".join(lines))
        elif el.name == "figure":
            img = el.find("img")
            if img:
                src = img.get("src") or img.get("data-src") or ""
                alt = img.get("alt") or img.get("title") or ""
                if src and not src.startswith("data:image"):
                    add_block(f"![{alt}]({src})")
            caption = el.find("figcaption")
            if caption:
                add_block(_inline_md(caption))

    deduped: list[str] = []
    for block in blocks:
        if not deduped or deduped[-1] != block:
            deduped.append(block)
    return "\n\n".join(deduped).strip() + "\n"


def yaml_escape(value: str | None) -> str:
    return (value or "").replace('"', '\\"')


def deterministic_created_date(post: dict, fallback: str | None = None) -> str:
    """Use published date as default created date for reproducible archives."""
    raw = post.get("post_date") or post.get("published_at") or ""
    return raw[:10] if raw else (fallback or "")


def article_markdown(post: dict, body_md: str, created_date: str | None = None) -> str:
    published = deterministic_created_date(post, created_date) or (created_date or "")
    created = created_date or published
    front = [
        "---",
        f'title: "{yaml_escape(post.get("title"))}"',
        f'source: "{yaml_escape(post.get("canonical_url"))}"',
        "author:",
        '  - "[[Nate]]"',
        f"published: {published}",
        f"created: {created}",
        f'description: "{yaml_escape(post.get("description"))}"',
        "---",
        "",
    ]
    return "\n".join(front) + body_md


def validate_article_markdown(markdown: str, required_phrases: list[str] | None = None) -> MarkdownValidation:
    required = required_phrases or DEFAULT_REQUIRED_PHRASES
    missing = [phrase for phrase in required if phrase not in markdown]
    forbidden = [phrase for phrase in FORBIDDEN_MARKDOWN_PHRASES if phrase in markdown]
    image_count = len(re.findall(r"!\[[^\]]*\]\([^\)]+\)", markdown))
    heading_count = len(re.findall(r"^#{1,6} ", markdown, flags=re.M))
    return MarkdownValidation(
        ok=not missing and not forbidden,
        missing_required=missing,
        present_forbidden=forbidden,
        image_count=image_count,
        heading_count=heading_count,
    )
