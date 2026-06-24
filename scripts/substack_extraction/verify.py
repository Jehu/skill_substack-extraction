from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Check:
    name: str
    ok: bool
    severity: str = "error"
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_export(out_dir: Path, require_media: bool = False, require_transcript: bool = False, require_links: bool = False) -> dict:
    checks: list[Check] = []

    def exists(rel: str, min_bytes: int = 1, severity: str = "error") -> None:
        path = out_dir / rel
        ok = path.exists() and path.is_file() and path.stat().st_size >= min_bytes
        checks.append(Check(f"file:{rel}", ok, severity, f"{path.stat().st_size} bytes" if path.exists() else "missing"))

    exists("index.md")
    exists("index.html")
    exists("metadata.json")
    exists("article.fragment.html")
    exists("media/image_urls.txt", 0, "warning")
    exists("media/audio_urls.txt", 0, "warning")
    exists("media/video_urls.txt", 0, "warning")

    metadata_path = out_dir / "metadata.json"
    if metadata_path.exists():
        try:
            metadata = _json(metadata_path)
            mv = metadata.get("markdown_validation") or {}
            checks.append(Check("markdown_validation", bool(mv.get("ok")), "error", json.dumps(mv, ensure_ascii=False)))
        except Exception as e:
            checks.append(Check("metadata_json_parse", False, "error", str(e)))

    md_path = out_dir / "index.md"
    if md_path.exists():
        md = md_path.read_text(encoding="utf-8", errors="replace")
        for forbidden in ["subscription-widget", "SubscribeWidgetToDOM", "data:image/svg", "clippings"]:
            checks.append(Check(f"forbidden:{forbidden}", forbidden not in md, "error"))

    if require_media:
        exists("media/download_plan.json")
        exists("media/download_results.json")
        if (out_dir / "media/download_results.json").exists():
            try:
                results = _json(out_dir / "media/download_results.json")
                failures = [r for items in results.values() for r in items if not r.get("ok") and r.get("strategy") != "mux-hls-candidate"]
                checks.append(Check("media_download_results", not failures, "error", f"{len(failures)} failures"))
            except Exception as e:
                checks.append(Check("media_results_json_parse", False, "error", str(e)))

    if require_transcript:
        exists("transcript.md")
        exists("transcript/manifest.json")
        if (out_dir / "transcript/manifest.json").exists():
            try:
                manifest = _json(out_dir / "transcript/manifest.json")
                checks.append(Check("transcript_manifest", bool(manifest.get("ok")), "error", manifest.get("error") or "ok"))
            except Exception as e:
                checks.append(Check("transcript_manifest_parse", False, "error", str(e)))

    if require_links:
        exists("linked/manifest.json")
        if (out_dir / "linked/manifest.json").exists():
            try:
                manifest = _json(out_dir / "linked/manifest.json")
                failures = [r for r in manifest.get("results", []) if not r.get("ok")]
                checks.append(Check("linked_results", not failures, "error", f"{len(failures)} failures"))
            except Exception as e:
                checks.append(Check("linked_manifest_parse", False, "error", str(e)))

    error_count = sum(1 for c in checks if not c.ok and c.severity == "error")
    warning_count = sum(1 for c in checks if not c.ok and c.severity == "warning")
    return {
        "ok": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "checks": [c.to_dict() for c in checks],
    }


def write_run_manifest(out_dir: Path, summary: dict, verification: dict) -> None:
    manifest = {
        "summary": summary,
        "verification": verification,
        "files": [
            {"path": str(p.relative_to(out_dir)), "bytes": p.stat().st_size}
            for p in sorted(out_dir.rglob("*")) if p.is_file()
        ],
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def write_verify_report(out_dir: Path, verification: dict) -> None:
    lines = ["# Verification Report", "", f"- **OK:** `{verification['ok']}`", f"- **Errors:** {verification['error_count']}", f"- **Warnings:** {verification['warning_count']}", "", "## Checks", ""]
    for c in verification["checks"]:
        mark = "✅" if c["ok"] else ("⚠️" if c["severity"] == "warning" else "❌")
        lines.append(f"- {mark} `{c['name']}` — {c['detail']}")
    (out_dir / "verification_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
