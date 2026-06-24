# Substack Extraction

Repeatable extractor for authorized single Substack posts and small batches. It exports clean Markdown/HTML, metadata, media URL lists, optional media downloads, optional Whisper transcripts, followed companion links, and verification reports.

> Use only with content you can lawfully access. This tool does not bypass paywalls, DRM, CAPTCHA, or access controls.

## Install

```bash
cd /a0/usr/projects/substack_extraction
python3 -m pip install -e .
```

Check:

```bash
substack-extract --version
substack-extract --help
```

## Single article

Fast article + linked Promptkit export, no large media/transcript:

```bash
substack-extract extract \
  --url 'https://natesnewsletter.substack.com/p/ai-loop-managers' \
  --cookies /a0/usr/uploads/cookies.txt \
  --output-root /a0/usr/workdir/substack_exports \
  --follow 'Grab the Prompts' \
  --follow-domain promptkit.natebjones.com
```

Full run with media and transcript:

```bash
substack-extract extract \
  --url 'https://natesnewsletter.substack.com/p/ai-loop-managers' \
  --cookies /a0/usr/uploads/cookies.txt \
  --output-root /a0/usr/workdir/substack_exports \
  --include-media \
  --transcribe \
  --follow 'Grab the Prompts' \
  --follow-domain promptkit.natebjones.com
```

The command prints the export directory on success.

## Batch

```bash
substack-extract batch --config examples/batch_ai_loop_managers.json --continue-on-error
```

Batch configs support global defaults and per-URL overrides:

```json
{
  "cookies": "/a0/usr/uploads/cookies.txt",
  "output_root": "/a0/usr/workdir/substack_exports",
  "include_media": false,
  "transcribe": false,
  "follow": ["Grab the Prompts"],
  "follow_domain": ["promptkit.natebjones.com"],
  "urls": [
    "https://natesnewsletter.substack.com/p/ai-loop-managers",
    {
      "url": "https://example.substack.com/p/another-post",
      "include_media": true
    }
  ]
}
```

Batch writes `batch_manifest.json` in `output_root`.

## Verify an existing export

```bash
substack-extract verify /a0/usr/workdir/substack_exports/natesnewsletter/2026-06-24_ai-loop-managers --require-links
```

Stricter checks:

```bash
substack-extract verify EXPORT_DIR --require-media --require-transcript --require-links --fail-on-warning
```

## Output

```text
{output_root}/{publication_slug}/{published_date}_{post_slug}/
├── index.md
├── index.html
├── metadata.json
├── extraction_report.md
├── verification_report.md
├── run_manifest.json
├── article.fragment.html
├── media/
│   ├── image_urls.txt
│   ├── audio_urls.txt
│   ├── video_urls.txt
│   ├── download_plan.json       # with --include-media
│   └── download_results.json    # with --include-media
├── transcript/                  # with --transcribe
│   └── manifest.json
├── transcript.md                # with --transcribe
└── linked/                      # with --follow/--follow-domain
    └── manifest.json
```

## Exit codes

| Command | `0` | `1` | `2` |
|---|---|---|---|
| `extract` | extraction completed | unhandled extraction error | CLI usage error |
| `batch` | all items succeeded | at least one item failed | CLI usage error |
| `verify` | verification passed | errors, or warnings with `--fail-on-warning` | CLI usage error |

## Debug / force

- `--debug` saves raw fetch artifacts such as `page.raw.html` and `fetch.headers.json`.
- `--force` removes/rebuilds an export folder for `extract`; for media/transcript stages it also re-downloads/re-runs instead of resuming.
