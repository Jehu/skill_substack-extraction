from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

from . import __version__
from .fetch import fetch_url
from .follow_links import follow_links_stage
from .markdown import article_markdown, body_html_to_markdown, html_document, validate_article_markdown
from .media import collect_media_urls, download_media, write_url_lists
from .models import ExtractOptions
from .parse_substack import output_dir_for, parse_post
from .report import write_report
from .transcript import transcribe
from .verify import verify_export, write_run_manifest, write_verify_report


def load_config(path: Path) -> dict:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    raise SystemExit("Only JSON config files are currently supported")


def options_from_args(args: argparse.Namespace) -> ExtractOptions:
    cfg = load_config(Path(args.config)) if args.config else {}
    url = args.url or cfg.get("url")
    cookies = args.cookies or cfg.get("cookies")
    output_root = args.output_root or cfg.get("output_root")
    if not url or not cookies or not output_root:
        raise SystemExit("Required: --url, --cookies, --output-root (or JSON --config with url/cookies/output_root)")
    return ExtractOptions(
        url=url,
        cookies=Path(cookies),
        output_root=Path(output_root),
        include_media=args.include_media or bool(cfg.get("include_media")),
        transcribe=args.transcribe or bool(cfg.get("transcribe")),
        follow=list(args.follow or cfg.get("follow") or []),
        follow_domain=list(args.follow_domain or cfg.get("follow_domain") or []),
        debug=args.debug or bool(cfg.get("debug")),
        force=args.force or bool(cfg.get("force")),
    )


def extract(options: ExtractOptions) -> Path:
    html_bytes, headers, final_url = fetch_url(options.url, options.cookies)
    html = html_bytes.decode("utf-8", errors="replace")
    parsed = parse_post(html, final_url)
    out_dir = output_dir_for(parsed, options.output_root)
    if out_dir.exists() and options.force:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if options.debug:
        (out_dir / "page.raw.html").write_bytes(html_bytes)
        (out_dir / "fetch.headers.json").write_text(json.dumps(headers, indent=2), encoding="utf-8")

    post = parsed.post
    body_html = post.get("body_html") or ""
    (out_dir / "article.fragment.html").write_text(body_html, encoding="utf-8")
    (out_dir / "index.html").write_text(html_document(post.get("title") or "", post.get("subtitle") or "", body_html), encoding="utf-8")
    body_md = body_html_to_markdown(body_html)
    created_date = (post.get("post_date") or "")[:10] or datetime.now().date().isoformat()
    index_md = article_markdown(post, body_md, created_date)
    (out_dir / "index.md").write_text(index_md, encoding="utf-8")
    markdown_validation = validate_article_markdown(index_md)

    urls = collect_media_urls(post, parsed.publication_host)
    media_dir = out_dir / "media"
    write_url_lists(media_dir, urls)

    metadata = {
        "title": post.get("title"),
        "subtitle": post.get("subtitle"),
        "description": post.get("description"),
        "url": post.get("canonical_url") or final_url,
        "slug": post.get("slug"),
        "post_id": post.get("id"),
        "publication_id": post.get("publication_id"),
        "post_date": post.get("post_date"),
        "audience": post.get("audience"),
        "type": post.get("type"),
        "media_url_counts": {k: len(v) for k, v in urls.items()},
        "markdown_validation": markdown_validation.__dict__,
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    media_results = None
    if options.include_media:
        media_results = download_media(out_dir, options.cookies, urls, force=options.force)

    followed = []
    if options.follow or options.follow_domain:
        followed = follow_links_stage(body_html, options.follow, options.follow_domain, post.get("canonical_url") or options.url, out_dir)

    transcript_result = None
    if options.transcribe:
        transcript_result = transcribe(out_dir, force=options.force)

    summary = {
        "url": options.url,
        "final_url": final_url,
        "title": post.get("title"),
        "post_id": post.get("id"),
        "output_dir": str(out_dir),
        "media_url_counts": {k: len(v) for k, v in urls.items()},
        "markdown_validation": markdown_validation.__dict__,
        "media_results": media_results,
        "followed_links": followed,
        "transcript": transcript_result,
    }
    verification = verify_export(out_dir, require_media=options.include_media, require_transcript=options.transcribe, require_links=bool(options.follow or options.follow_domain))
    summary["verification"] = verification
    write_verify_report(out_dir, verification)
    write_run_manifest(out_dir, summary, verification)
    write_report(out_dir, summary)
    return out_dir


def _list_value(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def batch_options_from_config(config_path: Path) -> tuple[list[ExtractOptions], dict]:
    cfg = load_config(config_path)
    urls = cfg.get("urls") or cfg.get("post_urls") or []
    if not urls:
        raise SystemExit("Batch config requires urls/post_urls")
    cookies = cfg.get("cookies")
    output_root = cfg.get("output_root")
    if not cookies or not output_root:
        raise SystemExit("Batch config requires cookies and output_root")

    options: list[ExtractOptions] = []
    for item in urls:
        if isinstance(item, str):
            item_cfg = {"url": item}
        elif isinstance(item, dict):
            item_cfg = item
        else:
            raise SystemExit(f"Invalid batch URL item: {item!r}")
        url = item_cfg.get("url")
        if not url:
            raise SystemExit(f"Batch URL item missing url: {item!r}")
        options.append(ExtractOptions(
            url=url,
            cookies=Path(item_cfg.get("cookies") or cookies),
            output_root=Path(item_cfg.get("output_root") or output_root),
            include_media=bool(item_cfg.get("include_media", cfg.get("include_media", False))),
            transcribe=bool(item_cfg.get("transcribe", cfg.get("transcribe", False))),
            follow=_list_value(item_cfg.get("follow", cfg.get("follow", []))),
            follow_domain=_list_value(item_cfg.get("follow_domain", cfg.get("follow_domain", []))),
            debug=bool(item_cfg.get("debug", cfg.get("debug", False))),
            force=bool(item_cfg.get("force", cfg.get("force", False))),
        ))
    return options, cfg


def run_batch(config_path: Path, continue_on_error: bool = False) -> dict:
    options, cfg = batch_options_from_config(config_path)
    output_root = Path(cfg["output_root"])
    output_root.mkdir(parents=True, exist_ok=True)
    results = []
    for i, opt in enumerate(options):
        try:
            out_dir = extract(opt)
            results.append({"index": i, "url": opt.url, "ok": True, "output_dir": str(out_dir)})
        except Exception as e:
            results.append({"index": i, "url": opt.url, "ok": False, "error": str(e)})
            if not continue_on_error:
                break
    manifest = {
        "config": str(config_path),
        "continue_on_error": continue_on_error,
        "total": len(options),
        "completed": len(results),
        "ok_count": sum(1 for r in results if r["ok"]),
        "error_count": sum(1 for r in results if not r["ok"]),
        "results": results,
    }
    (output_root / "batch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="substack-extract")
    parser.add_argument("--version", action="version", version=f"substack-extract {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    extract_p = sub.add_parser("extract", help="Extract one authorized Substack post")
    extract_p.add_argument("--config")
    extract_p.add_argument("--url")
    extract_p.add_argument("--cookies")
    extract_p.add_argument("--output-root")
    extract_p.add_argument("--include-media", action="store_true")
    extract_p.add_argument("--transcribe", action="store_true")
    extract_p.add_argument("--follow", action="append", default=[])
    extract_p.add_argument("--follow-domain", action="append", default=[])
    extract_p.add_argument("--debug", action="store_true")
    extract_p.add_argument("--force", action="store_true")

    verify_p = sub.add_parser("verify", help="Verify an existing export folder")
    verify_p.add_argument("path")
    verify_p.add_argument("--require-media", action="store_true")
    verify_p.add_argument("--require-transcript", action="store_true")
    verify_p.add_argument("--require-links", action="store_true")
    verify_p.add_argument("--fail-on-warning", action="store_true")

    batch_p = sub.add_parser("batch", help="Extract multiple authorized Substack posts from a JSON config")
    batch_p.add_argument("--config", required=True)
    batch_p.add_argument("--continue-on-error", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "extract":
        out = extract(options_from_args(args))
        print(out)
        return 0
    if args.command == "verify":
        out_dir = Path(args.path)
        verification = verify_export(out_dir, args.require_media, args.require_transcript, args.require_links)
        write_verify_report(out_dir, verification)
        print(json.dumps(verification, indent=2))
        if verification["error_count"] or (args.fail_on_warning and verification["warning_count"]):
            return 1
        return 0
    if args.command == "batch":
        manifest = run_batch(Path(args.config), continue_on_error=args.continue_on_error)
        print(json.dumps(manifest, indent=2))
        return 1 if manifest["error_count"] else 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
