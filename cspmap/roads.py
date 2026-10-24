"""Public road-analysis API, retained for existing callers."""

from .graph import augmented_graph
from .matching import anchor_key, match_points
from .models import Match, Segment
from .patches import assign_patches
from .road_download import download_osm
from .road_loaders import load_roads
from .road_network import Roads
from .road_validation import node_id, road_coordinate
from .routing import qualifying_connections

__all__ = [
    "Roads", "Segment", "Match", "load_roads", "download_osm",
    "road_coordinate", "node_id", "anchor_key", "match_points",
    "augmented_graph", "qualifying_connections", "assign_patches",
]
