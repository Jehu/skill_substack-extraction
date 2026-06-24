import io
import unittest
from contextlib import redirect_stdout

from substack_extraction import __version__
from substack_extraction.cli import build_parser, main


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
