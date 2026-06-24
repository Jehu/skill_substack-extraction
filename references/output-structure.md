# Output structure

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
