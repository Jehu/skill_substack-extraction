from __future__ import annotations

import json
from pathlib import Path


def write_report(out_dir: Path, summary: dict) -> None:
    lines = ["# Extraction Report", ""]
    lines.append(f"- **Source URL:** {summary.get('url')}")
    lines.append(f"- **Output path:** `{out_dir}`")
    lines.append(f"- **Title:** {summary.get('title')}")
    lines.append(f"- **Post ID:** {summary.get('post_id')}")
    verification = summary.get("verification") or {}
    if verification:
        lines.append("")
        lines.append("## Verification")
        lines.append("")
        lines.append(f"- **OK:** `{verification.get('ok')}`")
        lines.append(f"- **Errors:** {verification.get('error_count')}")
        lines.append(f"- **Warnings:** {verification.get('warning_count')}")
    lines.append("")
    lines.append("## Files")
    lines.append("")
    for path in sorted(out_dir.rglob("*")):
        if path.is_file():
            lines.append(f"- `{path.relative_to(out_dir)}` — {path.stat().st_size} bytes")
    lines.append("")
    lines.append("## Summary JSON")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(summary, ensure_ascii=False, indent=2))
    lines.append("```")
    (out_dir / "extraction_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
