import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from substack_extraction.follow_links import (
    discover_link_candidates,
    follow_links_stage,
    html_to_markdown_fallback,
    promptkit_markdown_endpoint,
    strip_frontmatter,
)


class FollowLinksTests(unittest.TestCase):
    def test_discover_candidates_dedupes_and_matches_text_or_domain(self):
        html = '''
        <a href="https://promptkit.natebjones.com/abc#one">Grab the Prompts</a>
        <a href="https://promptkit.natebjones.com/abc#two">Grab the Prompts duplicate fragment</a>
        <a href="/relative">Relative Grab the Prompts</a>
        <a href="https://other.example.com/nope">Nope</a>
        '''
        candidates = discover_link_candidates(html, ["Grab the Prompts"], ["promptkit.natebjones.com"], "https://natesnewsletter.substack.com/p/x")
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].url, "https://promptkit.natebjones.com/abc#one")
        self.assertEqual(candidates[1].url, "https://natesnewsletter.substack.com/relative")
        self.assertIn("text", candidates[0].matched_by)
        self.assertIn("domain", candidates[0].matched_by)

    def test_promptkit_markdown_endpoint(self):
        self.assertEqual(
            promptkit_markdown_endpoint("https://promptkit.natebjones.com/20260609_998_promptkit_1"),
            "https://promptkit.natebjones.com/api/assets/20260609_998_promptkit_1/markdown",
        )

    def test_strip_frontmatter(self):
        self.assertEqual(strip_frontmatter("---\ntitle: x\n---\nBody"), "Body")
        self.assertEqual(strip_frontmatter("Body"), "Body")

    def test_html_fallback_without_pandoc_uses_text(self):
        with patch("substack_extraction.follow_links.subprocess.run", side_effect=RuntimeError("missing pandoc")):
            md = html_to_markdown_fallback(b"<html><head><title>T</title><script>x</script></head><body><h1>Title</h1><p>Body</p></body></html>")
        self.assertIn("Title", md)
        self.assertIn("Body", md)
        self.assertNotIn("script", md)

    def test_follow_links_stage_native_markdown_and_manifest(self):
        body = '<a href="https://promptkit.natebjones.com/asset1">Grab the Prompts</a>'
        page_html = b"<html><head><title>Prompt Kit Page</title></head><body>html body</body></html>"
        native_md = b"---\ntitle: Native\n---\n# Prompt Kit\n\nPrompt 1 text"

        def fake_fetch(url):
            if url.endswith("/markdown"):
                return native_md, {}, url
            return page_html, {}, url

        with tempfile.TemporaryDirectory() as td, patch("substack_extraction.follow_links.fetch_url", side_effect=fake_fetch):
            out = Path(td)
            results = follow_links_stage(body, ["Grab the Prompts"], ["promptkit.natebjones.com"], "https://parent/post", out)
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0]["ok"])
            self.assertEqual(results[0]["strategy"], "native-markdown")
            index = out / results[0]["path"]
            self.assertIn("# Prompt Kit", index.read_text(encoding="utf-8"))
            manifest = json.loads((out / "linked/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["candidate_count"], 1)
            self.assertEqual(manifest["results"][0]["source_markdown"], "https://promptkit.natebjones.com/api/assets/asset1/markdown")


if __name__ == "__main__":
    unittest.main()
