# Substack Extraction Skill

A portable [Agent Skills](https://agentskills.io/specification)-style skill for exporting **authorized** Substack posts into clean local archives.

It can export:

- article Markdown and HTML
- metadata and verification reports
- image/audio/video URL manifests
- optional media downloads
- optional Whisper transcripts
- followed companion links such as Promptkit pages
- batch manifests for repeatable multi-post runs

> Use this only with content you can lawfully access: your own subscription, author/admin access, or explicit permission. This project does **not** bypass paywalls, DRM, CAPTCHA, or access controls.

## Repository shape

This repository is itself the skill folder:

```text
skill_substack-extraction/
├── SKILL.md                      # skill metadata and agent instructions
├── scripts/
│   ├── substack_extract.py        # portable CLI launcher
│   ├── requirements.txt           # runtime dependencies
│   └── substack_extraction/       # implementation package
├── assets/
│   └── batch_template.json
├── references/
│   ├── cookie-handling.md
│   └── output-structure.md
├── examples/
├── tests/
├── pyproject.toml
└── README.md
```

## Quick start

Clone the repo and install the one runtime dependency:

```bash
git clone git@github.com:Jehu/skill_substack-extraction.git
cd skill_substack-extraction
python3 -m pip install -r scripts/requirements.txt
```

Run without installing the package:

```bash
python3 scripts/substack_extract.py --help
python3 scripts/substack_extract.py --version
```

Optional editable install:

```bash
python3 -m pip install -e .
substack-extract --help
```

## Cookie input

For paywalled posts, provide an authorized cookie file from a browser session that has access to the post.

Recommended: Netscape `cookies.txt` file.

Do **not** paste cookie values into chat or commit them to git. The `.gitignore` excludes common cookie/env/secrets file names.

See [`references/cookie-handling.md`](references/cookie-handling.md).

## Single-post export

Fast article export with linked Promptkit pages, no large media download:

```bash
python3 scripts/substack_extract.py extract \
  --url 'https://example.substack.com/p/post-slug' \
  --cookies /path/to/cookies.txt \
  --output-root /path/to/substack_exports \
  --follow 'Grab the Prompts' \
  --follow-domain promptkit.example.com
  --follow-domain unlock-ai.natebjones.com
```

Full export with media and transcript:

```bash
python3 scripts/substack_extract.py extract \
  --url 'https://example.substack.com/p/post-slug' \
  --cookies /path/to/cookies.txt \
  --output-root /path/to/substack_exports \
  --include-media \
  --transcribe \
  --follow 'Grab the Prompts' \
  --follow-domain promptkit.example.com
  --follow-domain unlock-ai.natebjones.com
```

The command prints the export directory on success.

## Batch export

Copy the template:

```bash
cp assets/batch_template.json batch.json
```

Edit `batch.json`, then run:

```bash
python3 scripts/substack_extract.py batch --config batch.json --continue-on-error
```

Batch configs support global defaults plus per-URL overrides:

```json
{
  "cookies": "/path/to/cookies.txt",
  "output_root": "/path/to/substack_exports",
  "include_media": false,
  "transcribe": false,
  "follow": ["Grab the Prompts"],
  "follow_domain": ["promptkit.example.com", "unlock-ai.natebjones.com"],
  "urls": [
    "https://example.substack.com/p/one",
    {
      "url": "https://example.substack.com/p/two",
      "include_media": true,
      "transcribe": true
    }
  ]
}
```

The batch command writes:

```text
{output_root}/batch_manifest.json
```

## Verify an export

```bash
python3 scripts/substack_extract.py verify EXPORT_DIR --require-links
```

Strict verification:

```bash
python3 scripts/substack_extract.py verify EXPORT_DIR \
  --require-media \
  --require-transcript \
  --require-links \
  --fail-on-warning
```

Verification checks core files, Markdown validation, forbidden Substack widget residue, optional media manifests, optional transcript manifests, and optional linked-page manifests.

## Output structure

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

See [`references/output-structure.md`](references/output-structure.md).

## CLI reference

```bash
python3 scripts/substack_extract.py --help
python3 scripts/substack_extract.py extract --help
python3 scripts/substack_extract.py batch --help
python3 scripts/substack_extract.py verify --help
```

Commands:

| Command | Purpose |
|---|---|
| `extract` | Export one authorized Substack post |
| `batch` | Export multiple posts from a JSON config |
| `verify` | Verify an existing export folder |

Common options:

| Option | Meaning |
|---|---|
| `--cookies` | Netscape cookie file with authorized Substack access |
| `--output-root` | Root folder for exports |
| `--include-media` | Download images/audio/video where directly available |
| `--transcribe` | Run Whisper on audio, falling back to video |
| `--follow` | Follow links whose label contains this text |
| `--follow-domain` | Follow links from this domain |
| `--debug` | Save raw fetch artifacts |
| `--force` | Rebuild output / re-run resumable stages |

## Exit codes

| Command | `0` | `1` | `2` |
|---|---|---|---|
| `extract` | extraction completed | unhandled extraction error | CLI usage error |
| `batch` | all items succeeded | at least one item failed | CLI usage error |
| `verify` | verification passed | verification failed, or warning with `--fail-on-warning` | CLI usage error |

## Development

Install editable:

```bash
python3 -m pip install -e .
```

Run tests:

```bash
python3 -m unittest discover -s tests -v
```

Expected current result:

```text
Ran 25 tests
OK
```

## Publishing as an Agent Skill

This repo can be used directly as a skill folder because it contains `SKILL.md` at the root and all executable code under `scripts/`.

To install it into an Agent Skills-compatible environment, clone or copy the repository into that agent's skills directory.

For Agent Zero global skills, one option is:

```bash
git clone git@github.com:Jehu/skill_substack-extraction.git /a0/skills/substack-extraction
```

Skipped: Agent Zero plugin. Add one only if you need UI, settings, API handlers, or a native Agent Zero tool surface.
