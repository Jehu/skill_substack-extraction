import json
import unittest

from substack_extraction.parse_substack import extract_preloads, parse_post, safe_filename


class ParseSubstackTests(unittest.TestCase):
    def test_extract_preloads_json_parse_wrapper(self):
        payload = {"post": {"title": "T", "slug": "s", "canonical_url": "https://pub.substack.com/p/s"}}
        encoded = json.dumps(json.dumps(payload))[1:-1]
        html = f'<script>window._preloads = JSON.parse("{encoded}")</script>'
        self.assertEqual(extract_preloads(html)["post"]["title"], "T")
        parsed = parse_post(html, "https://pub.substack.com/p/s")
        self.assertEqual(parsed.publication_host, "pub.substack.com")
        self.assertEqual(parsed.slug, "s")

    def test_safe_filename(self):
        self.assertEqual(safe_filename("AI Loop Managers!"), "ai-loop-managers")


if __name__ == "__main__":
    unittest.main()
