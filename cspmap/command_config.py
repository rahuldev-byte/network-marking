"""Translate optional TOML settings into the existing validated CLI contract."""

import argparse
import sys
import tomllib
from pathlib import Path

PATH_FIELDS = {"splitters", "households", "roads", "output"}
BOOLEAN_FIELDS = {"auto_pilot", "download_osm", "points_only", "map"}
NUMBER_FIELDS = {"x_m", "snap_m", "ambiguity_m"}
LIST_FIELDS = {"bbox", "compare_x"}
COMMAND_FIELDS = {
    "profile": {"splitters", "households", "output", "map"},
    "run": (PATH_FIELDS | BOOLEAN_FIELDS | NUMBER_FIELDS | LIST_FIELDS) - {"map"},
}
CHOICE_GROUPS = (
    {"--bbox", "--auto-pilot"},
    {"--roads", "--download-osm", "--points-only"},
    {"--map", "--no-map"},
    {"--compare-x", "--no-compare-x"},
)


def overridden_options(argv):
    """An explicit CLI choice replaces the entire corresponding config choice."""
    options = {token.split("=", 1)[0] for token in argv if token.startswith("--")}
    for group in CHOICE_GROUPS:
        if options & group:
            options.update(group)
    return options


class CommandConfig:
    """Read simple named settings; paths are relative to the configuration file."""

    def __init__(self, path, command):
        self.path = Path(path).expanduser().resolve()
        with self.path.open("rb") as handle:
            self.values = tomllib.load(handle)
        unknown = self.values.keys() - COMMAND_FIELDS[command]
        if unknown:
            raise ValueError(
                f"{self.path}: unknown {command} settings: {', '.join(sorted(unknown))}"
            )

    def arguments(self, overrides):
        result = []
        for key, value in self.values.items():
            option = "--" + key.replace("_", "-")
            if option not in overrides:
                result.extend(self._argument(key, value, option))
        return result

    def _argument(self, key, value, option):
        if key in BOOLEAN_FIELDS:
            self._require(type(value) is bool, key, "a boolean")
            return [option] if value else []
        if key in PATH_FIELDS:
            self._require(isinstance(value, str) and bool(value.strip()), key, "a path")
            path = Path(value).expanduser()
            return [option, str((self.path.parent / path).resolve())]
        if key in NUMBER_FIELDS:
            self._require(type(value) in (int, float), key, "a number")
            return [option, str(value)]
        self._require(
            isinstance(value, list) and all(type(v) in (int, float) for v in value),
            key, "a list of numbers",
        )
        if key == "bbox":
            self._require(len(value) == 4, key, "four numbers")
        return [option, *(str(v) for v in value)] if value else []

    def _require(self, valid, key, expected):
        if not valid:
            raise ValueError(f"{self.path}: {key} must be {expected}")


def expand_arguments(argv=None):
    """Prepend file options so explicit flags retain ordinary argparse precedence."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMAND_FIELDS or {"--help", "-h"} & set(argv):
        return argv
    probe = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    probe.add_argument("--config", type=Path)
    options, _ = probe.parse_known_args(argv)
    if options.config is None:
        return argv
    config = CommandConfig(options.config, argv[0])
    return [argv[0], *config.arguments(overridden_options(argv)), *argv[1:]]
