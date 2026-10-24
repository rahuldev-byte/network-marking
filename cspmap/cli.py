"""Command parsing and terminal error handling for the mapper."""

import argparse
import json
import math
import sys
from pathlib import Path

from .command_config import expand_arguments
from .csv_input import DEFAULT_HOUSEHOLDS, DEFAULT_SPLITTERS
from .workflows import MappingApplication


def positive(value):
    """Parse a finite, strictly positive CLI distance."""
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def nonnegative(value):
    """Parse a finite CLI distance that may be zero."""
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("must be a finite nonnegative number")
    return number


class CommandLine:
    """Define the two user commands and validate their option combinations."""

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description=(
                "Map CSP infrastructure footprints from splitters, households "
                "and explicit road topology."
            )
        )
        commands = self.parser.add_subparsers(dest="command", required=True)
        for name in ("profile", "run"):
            command = commands.add_parser(name)
            self._inputs(command, name)
            if name == "profile":
                command.add_argument(
                    "--map", action=argparse.BooleanOptionalAction, default=False,
                    help="Also generate the full point overview (larger HTML file)",
                )
            else:
                self._region(command)
                self._roads(command)
                self._distances(command)

    def parse(self, argv=None):
        args = self.parser.parse_args(expand_arguments(argv))
        if args.command == "run":
            if not (args.roads or args.points_only or args.download_osm):
                args.download_osm = True  # OSM is the default topology source.
            if not args.points_only and args.x_m is None:
                self.parser.error(
                    "--x-m is required for road analysis; there is no business default"
                )
            if args.points_only and args.compare_x:
                self.parser.error("--compare-x needs roads")
        return args

    @staticmethod
    def _inputs(command, name):
        command.add_argument(
            "--config", type=Path,
            help="TOML settings file; explicit command-line options take precedence",
        )
        command.add_argument(
            "--splitters", type=Path, default=Path(DEFAULT_SPLITTERS)
        )
        command.add_argument(
            "--households", type=Path, default=Path(DEFAULT_HOUSEHOLDS)
        )
        command.add_argument("--output", type=Path, default=Path("outputs") / name)

    @staticmethod
    def _region(command):
        region = command.add_mutually_exclusive_group(required=True)
        region.add_argument(
            "--bbox", nargs=4, type=float,
            metavar=("WEST", "SOUTH", "EAST", "NORTH"),
        )
        region.add_argument(
            "--auto-pilot", action="store_true",
            help="Use the densest 0.02-degree splitter cell",
        )

    @staticmethod
    def _roads(command):
        source = command.add_mutually_exclusive_group()
        source.add_argument(
            "--roads", type=Path,
            help="Topology-aware GeoJSON, GeoPackage, Shapefile or Overpass JSON",
        )
        source.add_argument(
            "--download-osm", action="store_true",
            help="Download a buffered road graph from OSM Overpass (default)",
        )
        source.add_argument(
            "--points-only", action="store_true",
            help="Explicitly defer road matching and connectivity",
        )

    @staticmethod
    def _distances(command):
        command.add_argument(
            "--x-m", type=positive,
            help="Strict successive road-gap limit in metres; required with roads",
        )
        command.add_argument(
            "--snap-m", type=positive, default=30.0,
            help="Road match tolerance; exploratory default 30 m",
        )
        command.add_argument(
            "--ambiguity-m", type=nonnegative, default=2.0,
            help="Flag competing matches this close to the best offset; default 2 m",
        )
        comparisons = command.add_mutually_exclusive_group()
        comparisons.add_argument(
            "--compare-x", nargs="+", type=positive, default=[],
            help="Additional exploratory gap limits for sensitivity.json",
        )
        comparisons.add_argument(
            "--no-compare-x", dest="compare_x", action="store_const", const=[],
            help="Disable threshold comparisons inherited from a config file",
        )


def arguments(argv=None):
    """Preserve the existing parser entry point."""
    return CommandLine().parse(argv)


def run(args):
    """Execute one parsed command and print its terminal summary."""
    print(json.dumps(MappingApplication().execute(args)))


def main(argv=None):
    """Convert expected boundary errors into a useful nonzero exit code."""
    try:
        run(arguments(argv))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"cspmap: {exc}", file=sys.stderr)
        return 1
