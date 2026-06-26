---
name: substack-extraction
description: Export authorized Substack posts into Markdown, media URL manifests, optional media, transcripts, followed Promptkit links, and verification reports using the bundled portable CLI.
triggers:
  - "export substack article"
  - "scrape authorized substack"
  - "archive substack post"
  - "substack transcript"
  - "follow grab the prompts"
---

# Substack Extraction

Use this skill to archive Substack posts the user can lawfully access. Do not bypass paywalls, DRM, CAPTCHA, or access controls. Use only a user-provided authorized browser session/cookie file or content the user owns/has permission to access.

## Bundled CLI

The executable code is self-contained in `scripts/`.

Install dependency if needed:

```bash
python3 -m pip install -r scripts/requirements.txt
```

Run via the portable launcher:

```bash
python3 scripts/substack_extract.py --help
```

If this repo has been installed as a package, this also works:

```bash
substack-extract --help
```

## Single post

```bash
python3 scripts/substack_extract.py extract \
  --url 'https://example.substack.com/p/post-slug' \
  --cookies /path/to/cookies.txt \
  --output-root /path/to/substack_exports \
  --follow 'Grab the Prompts' \
  --follow-domain promptkit.example.com
  --follow-domain unlock-ai.natebjones.com
```

Add media/transcript only when requested:

```bash
python3 scripts/substack_extract.py extract \
  --url 'https://example.substack.com/p/post-slug' \
  --cookies /path/to/cookies.txt \
  --output-root /path/to/substack_exports \
  --include-media \
  --transcribe
```

## Batch

Copy `assets/batch_template.json`, fill in URLs/cookie path/output root, then run:

```bash
python3 scripts/substack_extract.py batch --config batch.json --continue-on-error
```

## Verify

```bash
python3 scripts/substack_extract.py verify EXPORT_DIR --require-links
```

Use stricter checks when relevant:

```bash
python3 scripts/substack_extract.py verify EXPORT_DIR \
  --require-media \
  --require-transcript \
  --require-links \
  --fail-on-warning
```

## Outputs

Each export writes `index.md`, `index.html`, `metadata.json`, `run_manifest.json`, `verification_report.md`, media URL lists, optional media files, optional transcript files, and optional linked companion pages under `linked/`.

See `references/output-structure.md` and `references/cookie-handling.md` for details.
