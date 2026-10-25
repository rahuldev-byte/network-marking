"""TOML configuration preserves CLI validation, overrides and path meaning."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from cspmap.cli import CommandLine, main


class CommandConfigTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.config = self.root / "pilot.toml"

    def parse(self, text, *overrides, command="run"):
        self.config.write_text(text)
        return CommandLine().parse([
            command, "--config", str(self.config), *overrides,
        ])

    def test_config_paths_are_relative_to_file_and_options_keep_their_types(self):
        args = self.parse('''
splitters = "inputs/splitter data.csv"
households = "inputs/households.csv"
roads = "inputs/roads.geojson"
output = "results"
auto_pilot = true
x_m = 100
compare_x = [50, 200]
''')
        self.assertEqual(args.splitters, self.root / "inputs/splitter data.csv")
        self.assertEqual(args.output, self.root / "results")
        self.assertEqual(args.x_m, 100)
        self.assertEqual(args.compare_x, [50, 200])

    def test_explicit_flags_override_values_and_mutually_exclusive_choices(self):
        args = self.parse('''
roads = "roads.geojson"
auto_pilot = true
x_m = 100
compare_x = [50, 200]
''', "--x-m=150", "--bbox", "77", "28", "77.01", "28.01",
            "--download-osm", "--no-compare-x", "--output", "new-output")
        self.assertEqual(args.x_m, 150)
        self.assertFalse(args.auto_pilot)
        self.assertEqual(args.bbox, [77, 28, 77.01, 28.01])
        self.assertTrue(args.download_osm)
        self.assertIsNone(args.roads)
        self.assertEqual(args.compare_x, [])
        self.assertEqual(args.output, Path("new-output"))

    def test_profile_map_can_be_disabled_explicitly(self):
        args = self.parse('map = true', "--no-map", command="profile")
        self.assertFalse(args.map)

    def test_abbreviated_flags_are_rejected_with_and_without_config(self):
        for command in ("run", "profile"):
            for configured in (False, True):
                with self.subTest(command=command, configured=configured):
                    errors = io.StringIO()
                    argv = [command, "--out", "somewhere"]
                    if command == "run":
                        argv += ["--auto-pilot", "--points-only"]
                    if configured:
                        self.config.write_text('output = "configured"')
                        argv += ["--config", str(self.config)]
                    with contextlib.redirect_stderr(errors), \
                            self.assertRaises(SystemExit):
                        CommandLine().parse(argv)
                    self.assertIn("unrecognized arguments: --out", errors.getvalue())

    def test_full_points_only_flag_overrides_configured_roads(self):
        args = self.parse('auto_pilot = true\nroads = "roads.geojson"',
                          "--points-only")
        self.assertTrue(args.points_only)
        self.assertIsNone(args.roads)

    def test_unknown_fields_and_wrong_types_are_rejected(self):
        for text in (
            'snap_distance = 30', 'auto_pilot = "yes"', 'roads = 123',
            'x_m = true', 'compare_x = [true]', 'bbox = [77, 28]',
            'output = ""', '[analysis]\nx_m = 100',
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.parse(text)
        with self.assertRaises(ValueError):
            self.parse('x_m = 100', command="profile")

    def test_distance_and_region_validation_still_apply(self):
        for text in (
            'auto_pilot = true\nroads = "roads.geojson"',
            'auto_pilot = true\npoints_only = true\nsnap_m = nan',
            'auto_pilot = true\nbbox = [77,28,77.01,28.01]\npoints_only = true',
        ):
            with (
                self.subTest(text=text), contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                self.parse(text)

    def test_bare_regional_flags_use_bundled_input_paths_and_osm(self):
        args = CommandLine().parse(["run", "--auto-pilot", "--x-m", "100"])
        self.assertEqual(args.splitters, Path("splitter_points.csv"))
        self.assertEqual(args.households, Path(
            "active_base_mobile_lat_long_time_added_20261022.csv"
        ))
        self.assertTrue(args.download_osm)

    def test_osm_is_default_but_explicit_roads_and_points_only_override(self):
        base = 'auto_pilot = true\nx_m = 100'
        args = self.parse(base)
        self.assertTrue(args.download_osm)
        self.assertIsNone(args.roads)
        self.assertFalse(args.points_only)
        args = self.parse(base, "--roads", "regional.geojson")
        self.assertFalse(args.download_osm)
        self.assertEqual(args.roads, Path("regional.geojson"))
        args = self.parse(base, "--points-only")
        self.assertFalse(args.download_osm)
        self.assertTrue(args.points_only)

    def test_help_does_not_require_loading_a_config(self):
        with (
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as e,
        ):
            CommandLine().parse(["run", "--config", "missing.toml", "--help"])
        self.assertEqual(e.exception.code, 0)

    def test_config_command_produces_outputs_and_records_the_override(self):
        (self.root / "splitters.csv").write_text(
            "partner_id,latitude,longitude\nowner,28,77\n"
        )
        (self.root / "households.csv").write_text("lat,long\n28,77\n")
        self.config.write_text('''
splitters = "splitters.csv"
households = "households.csv"
output = "result"
auto_pilot = true
points_only = true
snap_m = 30
''')
        with contextlib.redirect_stdout(io.StringIO()):
            status = main(["run", "--config", str(self.config), "--snap-m", "15"])
        self.assertEqual(status, 0)
        result = self.root / "result"
        self.assertTrue((result / "map.html").exists())
        self.assertEqual(json.loads((result / "config.json").read_text())["snap_m"], 15)
