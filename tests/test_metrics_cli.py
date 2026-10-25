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

    def test_report_failure_does_not_leave_partial_metrics(self):
        output = self.root / "metrics"
        metrics = {"per_csp": [], "matching": {"rate_pct_all_splitters": {}}}
        argv = ["--run", "unused", "--output", str(output)]
        with (
            patch("cspmap.metrics.analyse", return_value=metrics),
            patch("cspmap.metrics.write_report", side_effect=OSError("disk error")),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(main(argv), 1)
        self.assertEqual(list(output.iterdir()), [])
        with (
            patch("cspmap.metrics.analyse", return_value=metrics),
            patch("cspmap.metrics.write_report"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(main(argv), 0)
        self.assertTrue((output / "metrics.json").exists())
