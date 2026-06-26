import unittest
from pathlib import Path

from substack_extraction.markdown import (
    article_markdown,
    body_html_to_markdown,
    deterministic_created_date,
    validate_article_markdown,
)


class MarkdownTests(unittest.TestCase):
    def test_body_html_to_markdown_removes_substack_widgets_and_keeps_content(self):
        html = '''
        <p>Hello <strong>world</strong>.</p>
        <div class="subscription-widget-wrap-editor">SubscribeWidgetToDOM</div>
        <h2>The work around the prompt</h2>
        <ul><li><strong>One.</strong> Item</li></ul>
        <figure><img src="https://example.com/image.jpeg" alt="Alt text"></figure>
        '''
        md = body_html_to_markdown(html)
        self.assertIn("Hello **world**.", md)
        self.assertIn("## The work around the prompt", md)
        self.assertIn("- **One.** Item", md)
        self.assertIn("![Alt text](https://example.com/image.jpeg)", md)
        self.assertNotIn("subscription-widget", md)
        self.assertNotIn("SubscribeWidgetToDOM", md)

    def test_article_markdown_frontmatter_is_deterministic_and_has_no_clippings_tag(self):
        post = {
            "title": "Title",
            "canonical_url": "https://example.com/p/test",
            "post_date": "2026-06-24T00:00:00Z",
            "description": "Description",
        }
        md1 = article_markdown(post, "Body\n", deterministic_created_date(post))
        md2 = article_markdown(post, "Body\n", deterministic_created_date(post))
        self.assertEqual(md1, md2)
        self.assertTrue(md1.startswith("---\n"))
        self.assertIn('title: "Title"', md1)
        self.assertIn("published: 2026-06-24", md1)
        self.assertIn("created: 2026-06-24", md1)
        self.assertNotIn("tags:", md1)
        self.assertNotIn("clippings", md1)

    def test_article_excerpt_regression_validation(self):
        html = Path("tests/fixtures/article_excerpt.html").read_text(encoding="utf-8")
        body_md = body_html_to_markdown(html)
        post = {
            "title": "The Five Questions That Turn a Messy Task Into an AI Loop (+ the prompts to map yours)",
            "canonical_url": "https://natesnewsletter.substack.com/p/ai-loop-managers",
            "post_date": "2026-06-24T13:01:22.720Z",
            "description": "Watch now | Apps taught us to open the right square.",
        }
        md = article_markdown(post, body_md, deterministic_created_date(post))
        validation = validate_article_markdown(md)
        self.assertTrue(validation.ok, validation)
        self.assertEqual(validation.missing_required, [])
        self.assertEqual(validation.present_forbidden, [])
        self.assertEqual(validation.image_count, 1)
        self.assertGreaterEqual(validation.heading_count, 7)
        self.assertIn("05-map-of-intentions", md)
        self.assertNotIn("data:image/svg", md)

    def test_validation_is_not_tied_to_specific_article_headings(self):
        md = article_markdown(
            {
                "title": "Different Article",
                "canonical_url": "https://example.com/p/different",
                "post_date": "2026-06-26T00:00:00Z",
                "description": "Description",
            },
            "## Completely Different Heading\n\nBody text.\n",
            "2026-06-26",
        )
        validation = validate_article_markdown(md)
        self.assertTrue(validation.ok, validation)
        self.assertEqual(validation.missing_required, [])

    def test_validation_still_supports_explicit_required_phrases_for_fixtures(self):
        validation = validate_article_markdown("Body only", required_phrases=["Expected fixture phrase"])
        self.assertFalse(validation.ok)
        self.assertEqual(validation.missing_required, ["Expected fixture phrase"])


if __name__ == "__main__":
    unittest.main()
