import io
import unittest
import unittest.mock
from contextlib import redirect_stdout

from substack_extraction import __version__
from substack_extraction.cli import build_parser, main, options_from_args


class CliTests(unittest.TestCase):
    def test_version_flag(self):
        buf = io.StringIO()
        with self.assertRaises(SystemExit) as cm, redirect_stdout(buf):
            main(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn(__version__, buf.getvalue())

    def test_parser_has_expected_subcommands(self):
        help_text = build_parser().format_help()
        self.assertIn("extract", help_text)
        self.assertIn("verify", help_text)
        self.assertIn("batch", help_text)

    def test_output_root_can_come_from_env(self):
        args = build_parser().parse_args([
            "extract",
            "--url", "https://example.com/p/post",
            "--cookies", "/cookies.txt",
        ])
        with unittest.mock.patch.dict("os.environ", {"SUBSTACK_EXPORT_ROOT": "/env/exports"}, clear=False):
            options = options_from_args(args)
        self.assertEqual(str(options.output_root), "/env/exports")


    def test_cookies_can_come_from_env(self):
        args = build_parser().parse_args([
            "extract",
            "--url", "https://example.com/p/post",
            "--output-root", "/exports",
        ])
        with unittest.mock.patch.dict("os.environ", {"SUBSTACK_COOKIES": "/env/cookies.txt"}, clear=False):
            options = options_from_args(args)
        self.assertEqual(str(options.cookies), "/env/cookies.txt")

    def test_explicit_cookies_override_env(self):
        args = build_parser().parse_args([
            "extract",
            "--url", "https://example.com/p/post",
            "--cookies", "/manual/cookies.txt",
            "--output-root", "/exports",
        ])
        with unittest.mock.patch.dict("os.environ", {"SUBSTACK_COOKIES": "/env/cookies.txt"}, clear=False):
            options = options_from_args(args)
        self.assertEqual(str(options.cookies), "/manual/cookies.txt")

    def test_explicit_output_root_overrides_env(self):
        args = build_parser().parse_args([
            "extract",
            "--url", "https://example.com/p/post",
            "--cookies", "/cookies.txt",
            "--output-root", "/manual/exports",
        ])
        with unittest.mock.patch.dict("os.environ", {"SUBSTACK_EXPORT_ROOT": "/env/exports"}, clear=False):
            options = options_from_args(args)
        self.assertEqual(str(options.output_root), "/manual/exports")
