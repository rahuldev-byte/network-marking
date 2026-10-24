"""Metrics command failures preserve outputs and report useful exit statuses."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cspmap.metrics import main


class MetricsCommandTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def test_missing_run_reports_an_error_without_a_traceback(self):
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            status = main([
                "--run", str(self.root / "missing"),
                "--output", str(self.root / "metrics"),
            ])
        self.assertEqual(status, 1)
        self.assertIn("cspmap.metrics:", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    def test_occupied_or_file_destination_is_rejected_before_analysis(self):
        existing = self.root / "report.txt"
        existing.write_text("preserve this")
        for output in (existing, self.root):
            with (
                self.subTest(output=output),
                contextlib.redirect_stderr(io.StringIO()),
                patch("cspmap.metrics.analyse") as analyse,
            ):
                status = main(["--run", "unused", "--output", str(output)])
                self.assertEqual(status, 1)
                analyse.assert_not_called()
        self.assertEqual(existing.read_text(), "preserve this")
