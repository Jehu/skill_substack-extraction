# Reproducible Substack Extraction Plan

## Goal

Build a repeatable pipeline that exports one authorized Substack post into a stable local folder structure, including:

- article Markdown and HTML
- metadata JSON
- images
- audio and/or video
- transcript files
- followed companion links such as Prompt Kit pages
- logs and verification summaries

This project assumes the user has lawful access to the target content through a subscription, author/admin access, or explicit permission. The system must not bypass paywalls, DRM, CAPTCHA, or access controls.

## Current successful manual run

Source post:

`https://natesnewsletter.substack.com/p/ai-loop-managers`

Export folder:

`/a0/usr/workdir/substack_exports/natesnewsletter/2026-06-24_ai-loop-managers/`

Generated assets:

- `index.md` — cleaned article Markdown with frontmatter
- `index.html` — article HTML
- `metadata.json` — post metadata
- `media/images/` — article images
- `media/audio/audio_01.mp3` — full audio
- `media/video/video_01.mp4` — full video
- `transcript.md` and `transcript/audio_01.*` — Whisper transcript outputs
- `linked/00_promptkit/index.md` — followed Prompt Kit page as Markdown

## Proposed directory structure

```text
substack_exports/
└── {publication_slug}/
    └── {published_date}_{post_slug}/
        ├── index.md
        ├── index.html
        ├── metadata.json
        ├── extraction_report.md
        ├── article.fragment.html
        ├── media/
        │   ├── images/
        │   ├── audio/
        │   ├── video/
        │   ├── image_urls.txt
        │   ├── audio_urls.txt
        │   └── video_urls.txt
        ├── transcript/
        │   ├── audio_01.txt
        │   ├── audio_01.srt
        │   ├── audio_01.vtt
        │   ├── audio_01.tsv
        │   └── audio_01.json
        ├── transcript.md
        └── linked/
            └── {nn}_{link_slug}/
                ├── index.md
                ├── metadata.json
                └── page.raw.html optional/debug only
```

## Pipeline phases

### 1. Input configuration

Inputs should be explicit and stored in a run config:

- `post_url`
- `cookies_file`
- `output_root`
- `include_media`: true/false
- `include_transcript`: true/false
- `follow_link_patterns`, e.g. `promptkit.natebjones.com`, link text matching `Grab the Prompts`
- `keep_raw_debug_files`: true/false

Suggested command shape:

```bash
substack-extract \
  --url 'https://natesnewsletter.substack.com/p/ai-loop-managers' \
  --cookies /path/to/cookies.txt \
  --output-root /a0/usr/workdir/substack_exports \
  --include-media \
  --transcribe \
  --follow 'Grab the Prompts' \
  --follow-domain promptkit.natebjones.com
```

### 2. Authenticated fetch

Use `curl` or Python `requests` with Netscape cookie support.

Save:

- `page.raw.html` when debug mode is enabled
- `fetch.headers.txt` when debug mode is enabled

Verify:

- HTTP status is 200
- title matches expected post
- no login/paywall markers such as `Sign in` or `Subscribe to continue reading`
- embedded preload data exists: `window._preloads = JSON.parse(...)`

### 3. Parse Substack preload data

Extract `window._preloads` from the HTML and parse it as JSON.

From `data.post`, collect:

- `title`
- `subtitle`
- `description`
- `canonical_url`
- `slug`
- `id`
- `publication_id`
- `post_date`
- `audience`
- `body_html`
- `cover_image`
- `podcast_url`
- `podcastUpload`
- `videoUpload`

This should be the canonical source for article content, not the rendered page DOM.

### 4. Generate article files

Generate:

- `article.fragment.html` from `post.body_html`
- `index.html` as a standalone HTML document
- `index.md` as clean Markdown
- `metadata.json`

Markdown cleanup rules:

- include useful frontmatter: title, source, author, published, created, description
- do not add generic Obsidian tags like `clippings`
- remove Substack subscription widgets
- remove data-URI SVG controls
- keep real images as Markdown image links
- preserve headings, bullets, links, bold/italic text
- verify required article headings/phrases

### 5. Download media

Images:

- extract from `body_html`, `cover_image`, `podcast_episode_image_url`
- download into `media/images/`

Audio:

- prefer `post.podcast_url`
- save to `media/audio/audio_01.mp3`

Video:

- if `videoUpload.id` exists, use authorized endpoint:

```text
https://{publication_host}/api/v1/video/upload/{video_upload_id}/src
```

- save to `media/video/video_01.mp4`
- verify with `ffprobe`

Do not attempt DRM bypass. If direct authorized endpoints fail and only protected/DRM playback remains, record that as unsupported.

### 6. Transcription

If `media/audio/audio_01.mp3` exists, transcribe from audio.

If no audio exists but video exists, extract/transcribe from video.

Output:

- `transcript/audio_01.txt`
- `transcript/audio_01.srt`
- `transcript/audio_01.vtt`
- `transcript/audio_01.tsv`
- `transcript/audio_01.json`
- `transcript.md`

Current working command:

```bash
whisper media/audio/audio_01.mp3 \
  --language English \
  --task transcribe \
  --model small \
  --output_dir transcript \
  --output_format all \
  --verbose False
```

### 7. Follow companion links

Find links by:

- anchor text: `Grab the Prompts`, `Grab the prompt kit`
- domain allowlist: `promptkit.natebjones.com`

For Prompt Kit pages:

1. Fetch normal page.
2. Detect native Markdown endpoint:

```text
/api/assets/{asset_id}/markdown
```

3. Prefer native Markdown over HTML conversion.
4. Save to:

```text
linked/{nn}_{slug}/index.md
```

For the current article, this produced:

`linked/00_promptkit/index.md`

### 8. Verification report

Every run should produce `extraction_report.md` with:

- source URL
- output path
- HTTP status
- article title
- file sizes
- media counts
- transcript status
- followed links
- warnings/failures
- cleanup status

## Implementation plan

### Milestone 1 — Scripted single-post extractor

Create a Python CLI in this project:

```text
substack_extraction/
├── pyproject.toml
├── README.md
├── src/substack_extraction/
│   ├── __init__.py
│   ├── cli.py
│   ├── fetch.py
│   ├── parse_substack.py
│   ├── markdown.py
│   ├── media.py
│   ├── transcript.py
│   ├── follow_links.py
│   └── report.py
├── tests/
└── docs/
```

Start with one command:

```bash
python -m substack_extraction.cli extract --config run.yaml
```

### Milestone 2 — Deterministic Markdown generation

Move the current BeautifulSoup-based cleanup into `markdown.py` and add regression checks for:

- frontmatter has no `tags: clippings`
- key headings are present
- subscription widgets are absent
- image Markdown is preserved

### Milestone 3 — Media download abstraction

Implement media download strategies:

- image downloader
- Substack audio URL downloader
- Substack video `/api/v1/video/upload/{id}/src` downloader
- ffprobe verification

### Milestone 4 — Transcription wrapper

Add a transcription wrapper that:

- uses audio if present
- falls back to video if audio is absent
- supports `whisper` CLI initially
- writes `transcript.md`
- skips if transcript already exists unless `--force`

### Milestone 5 — Link-following plugins

Implement a small plugin/handler interface:

- `PromptKitHandler`
- generic HTML-to-Markdown fallback

The Prompt Kit handler should prefer native Markdown endpoints.

### Milestone 6 — Run reports and cleanup

Add final verification and optional cleanup:

- keep raw files only with `--debug`
- always keep useful URL lists and metadata
- write `extraction_report.md`

## Open decisions

1. Should cookies be read only from a Netscape `cookies.txt`, or should browser storage-state JSON also be supported?
2. Should raw HTML/debug files be deleted by default after successful extraction?
3. Should transcripts default to Whisper `small`, or should the model be configurable per run?
4. Should followed links be limited to known safe domains by default?
5. Should output be optimized for Obsidian, plain Markdown archives, or both via templates?

## Next concrete step

Build Milestone 1 as a minimal CLI using the successful current extraction as the reference case.

## Milestone 2 implementation notes

Implemented deterministic Markdown generation with regression checks:

- `src/substack_extraction/markdown.py` owns all Substack HTML-to-Markdown cleanup.
- `article_markdown()` uses stable published/created dates from post metadata instead of wall-clock time where possible.
- `validate_article_markdown()` checks required article sections, forbidden widget residue, image count, and heading count.
- Regression fixture `tests/fixtures/article_excerpt.html` covers headings, lists, links, image preservation, and widget removal.
- CLI reports Markdown validation in both `metadata.json` and `extraction_report.md` summary JSON.

## Milestone 3 implementation notes

Implemented the media download abstraction:

- `MediaItem` and `MediaResult` dataclasses describe planned media downloads and per-item outcomes.
- `build_media_plan()` turns collected URLs into deterministic local paths and named strategies.
- `download_media()` writes `media/download_plan.json` and `media/download_results.json`.
- Existing completed files are skipped unless `--force` is supplied, making media stages resumable.
- Direct Substack image/audio/video downloads are supported.
- Mux/HLS candidates are recorded as fallback candidates but intentionally not downloaded until a dedicated HLS strategy is added.
- Tests cover URL collection, deterministic plans, extension inference, existing-file resume/skip behavior, and missing-file download dispatch.

## Milestone 4 implementation notes

Implemented transcription stage hardening:

- `select_transcript_source()` prefers `media/audio/audio_01.mp3` and falls back to `media/video/video_01.mp4`.
- `transcribe()` is resumable: it skips existing transcript text unless `--force` is used.
- `transcript/manifest.json` records source, source kind, command, outputs, model, language, skip status, and errors.
- `transcript.md` is regenerated from the transcript text after successful or skipped runs.
- Whisper output is captured in `transcript/whisper.log`.
- Tests mock Whisper instead of running real transcription.

## Milestone 5 implementation notes

Implemented link-following / companion page hardening:

- `LinkCandidate` and `FollowResult` dataclasses structure discovery and results.
- `discover_link_candidates()` supports text pattern matching, domain allowlist matching, relative URLs, and fragment-insensitive deduplication.
- `follow_links_stage()` owns the full linked-page stage and writes `linked/manifest.json`.
- Promptkit native Markdown endpoints are preferred and recorded as `source_markdown`.
- HTML fallback uses Pandoc when available and BeautifulSoup text extraction otherwise.
- Backward-compatible `discover_links()` and `follow_link()` wrappers remain available.
- Tests cover discovery/deduplication, Promptkit endpoint derivation, frontmatter stripping, HTML fallback, native Markdown export, and manifest writing.

## Milestone 6 implementation notes

Implemented reports / verification hardening:

- `verify_export()` performs machine-readable checks for core article files, Markdown validation, forbidden residue, optional media, transcript, and linked-page manifests.
- `verification_report.md` gives a compact human-readable check report.
- `run_manifest.json` records summary, verification, and exported file inventory.
- `substack-extract verify <path>` verifies an existing export folder.
- `--require-media`, `--require-transcript`, `--require-links`, and `--fail-on-warning` control strictness.
- `extraction_report.md` now includes verification status.

## Milestone 7 implementation notes

Implemented config / batch ergonomics:

- `batch_options_from_config()` builds per-post `ExtractOptions` from one JSON config.
- `substack-extract batch --config batch.json` extracts multiple authorized post URLs.
- Batch configs support global defaults plus per-URL overrides.
- `--continue-on-error` keeps later URLs running after a failed item.
- `batch_manifest.json` records total, completed, ok/error counts, and per-URL results.
- Example config: `examples/batch_ai_loop_managers.json`.
- Tests cover config parsing, per-URL overrides, continuation behavior, and manifest writing.

## Milestone 8 implementation notes

Implemented CLI polish / usability:

- Added `substack-extract --version`.
- Updated `README.md` with install, single article, full media/transcript, batch, verify, output tree, exit codes, and debug/force behavior.
- Added CLI tests for version output and advertised subcommands.

## Portable skill packaging notes

The repository root is now an agentskills.io-style self-contained skill folder:

- `SKILL.md` contains skill metadata and usage instructions.
- `scripts/substack_extraction/` contains the Python package implementation.
- `scripts/substack_extract.py` is the portable launcher for agents that do not install the package.
- `scripts/requirements.txt` lists runtime dependencies.
- `assets/batch_template.json` is a copyable batch config template.
- `references/` contains optional operational details.

The project can still be installed with `python3 -m pip install -e .`; `pyproject.toml` now uses `scripts/` as the package root.
