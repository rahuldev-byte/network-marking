"""Shared domain records; no input, routing, or presentation logic."""

from dataclasses import dataclass, field
from typing import NamedTuple, TypedDict

Coordinate = list[float]
MetricCoordinate = tuple[float, float]


class Connection(TypedDict):
    """A qualifying route with source-record and road-piece traceability."""

    from_splitter: str
    to_splitter: str
    partner_id: str
    distance_m: float
    coordinates: list[Coordinate]
    piece_ids: list[str]


class Patch(TypedDict):
    """A deterministic connected component belonging to one owner."""

    patch_id: str
    partner_id: str
    splitter_count: int
    splitter_ids: list[str]
    isolated: bool


@dataclass
class Point:
    """A source record whose ownership and original location are retained."""

    id: str
    lat: float | None
    lon: float | None
    partner: str = ""
    flags: list[str] = field(default_factory=list)
    status: str = "roads_unavailable"
    offset_m: float | None = None
    road_id: str = ""
    patch: str = ""

    @property
    def valid(self) -> bool:
        """Whether coordinate validation supplied both components."""
        return self.lat is not None and self.lon is not None

    def reset_match(self) -> None:
        """Discard derived state before a fresh matching pass."""
        self.offset_m = None
        self.road_id = ""
        self.patch = ""


@dataclass(frozen=True)
class Segment:
    """One original road edge between explicit topology nodes."""

    id: str
    u: str
    v: str
    a: Coordinate
    b: Coordinate
    xy_a: MetricCoordinate
    xy_b: MetricCoordinate
    length: float
    road_id: str


@dataclass(frozen=True)
class Match:
    """An accepted position partway along an original road segment."""

    segment: int
    t: float
    offset: float
    anchor: str


class RoadGraph(NamedTuple):
    """Routing graph with named fields and legacy tuple compatibility."""

    adjacency: dict[str, list[tuple[str, float, str]]]
    coordinates: dict[str, Coordinate]
    pieces: dict[str, dict]
