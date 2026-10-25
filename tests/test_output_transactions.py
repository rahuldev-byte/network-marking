"""Failed commands can be retried without touching source or existing results."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cspmap.cli import main
from cspmap.run_output import staged_output


class OutputTransactionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.splitters = self.root / "s.csv"
        self.households = self.root / "h.csv"
        self.splitters.write_text("partner_id,latitude,longitude\nowner,28,77\n")
        self.households.write_text("lat,long\n28,77\n")
        self.output = self.root / "result"
        self.inputs = ["--splitters", str(self.splitters), "--households",
                       str(self.households), "--output", str(self.output)]

    def run_command(self, arguments):
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return main(arguments)

    def test_invalid_region_can_be_corrected_and_retried_in_same_directory(self):
        base = ["run", *self.inputs, "--points-only", "--bbox"]
        self.assertEqual(self.run_command(base + ["78", "28", "77", "29"]), 1)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.run_command(base + ["76.9", "27.9", "77.1", "28.1"]), 0)
        self.assertTrue((self.output / "map.html").is_file())

    def test_render_failure_leaves_no_partial_outputs_and_allows_retry(self):
        for command, target, extra in (
            ("profile", "cspmap.workflows.write_map", ["--map"]),
            ("run", "cspmap.run_output.write_map", ["--auto-pilot", "--points-only"]),
        ):
            with self.subTest(command=command):
                self.output = self.root / command
                argv = [command, *self.inputs, *extra, "--output", str(self.output)]
                before = [p.read_bytes() for p in (self.splitters, self.households)]
                with patch(target, side_effect=ValueError("render failed")):
                    self.assertEqual(self.run_command(argv), 1)
                self.assertEqual(list(self.output.iterdir()), [])
                self.assertEqual(list(self.root.glob(f".{command}-*")), [])
                self.assertEqual(self.run_command(argv), 0)
                self.assertEqual([p.read_bytes() for p in
                                  (self.splitters, self.households)], before)

    def test_existing_and_concurrently_added_results_are_preserved(self):
        self.output.mkdir()
        marker = self.output / "keep.txt"
        marker.write_text("existing")
        with self.assertRaisesRegex(ValueError, "not empty"):
            with staged_output(self.output):
                self.fail("Occupied destination should fail before work")
        self.assertEqual(marker.read_text(), "existing")
        other = self.root / "concurrent"
        with self.assertRaisesRegex(ValueError, "not empty"):
            with staged_output(other) as staging:
                (staging / "new.txt").write_text("new")
                (other / "keep.txt").write_text("concurrent")
        self.assertEqual((other / "keep.txt").read_text(), "concurrent")
        self.assertFalse((other / "new.txt").exists())

    def test_downloaded_road_path_points_to_published_snapshot(self):
        document = {"elements": [
            {"type": "node", "id": 1, "lon": 77, "lat": 28},
            {"type": "node", "id": 2, "lon": 77.001, "lat": 28},
            {"type": "way", "id": 3, "nodes": [1, 2],
             "tags": {"highway": "residential"}},
        ]}

        def download(bbox, padding, path):
            path.write_text(json.dumps(document))

        with patch("cspmap.workflows.download_osm", side_effect=download):
            self.assertEqual(self.run_command([
                "run", *self.inputs, "--auto-pilot", "--x-m", "100",
            ]), 0)
        config = json.loads((self.output / "config.json").read_text())
        self.assertEqual(Path(config["road_file"]), self.output / "osm_roads.json")
        self.assertTrue(Path(config["road_file"]).is_file())


if __name__ == "__main__":
    unittest.main()
