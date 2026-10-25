"""Draw a single provider network over the actual road graph in Folium."""

from collections import defaultdict
from html import escape

import folium

from .geospatial import feature_frame
from .serialization import feature


def provider_colour(owner):
    """Give a provider a stable display colour across regenerated maps."""
    value = 2166136261
    for character in owner:
        value = ((value ^ ord(character)) * 16777619) & 0xFFFFFFFF
    return f"hsl({value % 360},57%,38%)"


def display_properties(properties):
    """Escape display text before Folium inserts properties into HTML popups."""
    return {
        key: escape("; ".join(value)) if isinstance(value, list)
        else escape(value) if isinstance(value, str) else value
        for key, value in properties.items()
    }


def needs_review(point):
    """Distinguish unresolved/flagged records from an unanalysed point overview."""
    return bool(point["flags"]) or point["status"] in {
        "ambiguous_road_match", "no_road_within_tolerance",
        "source_review_required", "invalid_coordinates",
    }


def spatial_layer(features, name, colour, popup_fields=(), point=False, style=None):
    """Pass a CRS-aware GeoDataFrame to Folium rather than hand-drawing geometry."""
    options = {
        "color": colour, "weight": 1 if point else 2.5,
        "fillColor": colour, "fillOpacity": 0.8, **(style or {}),
    }
    popup = folium.GeoJsonPopup(fields=list(popup_fields)) if popup_fields else None
    return folium.GeoJson(
        feature_frame(features), name=name, control=False,
        style_function=lambda row: options,
        marker=folium.CircleMarker(radius=4, fill=True) if point else None,
        popup=popup,
    )


class ResultLayers:
    """Keep all provider routes, road snaps, and nodes in one filterable network.

    Each provider is a single child group of the visible network layer. Filtering
    a provider therefore hides its links AND its endpoints together; review
    styling never creates duplicate markers. The underlying OSM road geometry
    and owner-unknown household reference remain separate contextual overlays.
    """

    def __init__(self, data):
        self.data = data
        self.groups = {
            "network": folium.FeatureGroup(name="Provider network · nodes and links"),
        }
        self.entries = []
        self.points_by_owner = defaultdict(list)
        self.routes_by_owner = defaultdict(list)
        for point in data["splitters"]:
            self.points_by_owner[point["partner"]].append(point)
        for route in data["connections"]:
            self.routes_by_owner[route["partner_id"]].append(route)

    def add_to(self, map_view):
        self._context(map_view)
        owners = sorted(self.points_by_owner)
        for index, owner in enumerate(owners):
            provider = folium.FeatureGroup(name="Provider network", control=False)
            # Routes and GPS-to-road snap connectors are drawn before nodes.
            self._routes(owner, provider)
            self._snaps(owner, provider)
            self._splitters(owner, provider)
            provider.add_to(self.groups["network"])
            self.entries.append({
                "owner": index, "parent": self.groups["network"].get_name(),
                "layer": provider.get_name(),
                "point_count": len(self.points_by_owner[owner]),
            })
        if owners:
            self.groups["network"].add_to(map_view)
        return owners, self.entries

    def _context(self, map_view):
        roads = [feature({"type": "LineString", "coordinates": line}, {})
                 for line in self.data["roads"]]
        if roads:
            source = "OSM" if self.data["osm"] else "Company"
            group = folium.FeatureGroup(name=f"Road graph · {source} geometry")
            spatial_layer(roads, "Road topology", "#65746e", style={
                "weight": 1.25, "opacity": 0.27,
            }).add_to(group)
            group.add_to(map_view)
        households = [feature({"type": "Point", "coordinates": point}, {})
                      for point in self.data["households"]]
        if households:
            group = folium.FeatureGroup(
                name="Households · owner unknown", show=not self.data["splitters"],
            )
            spatial_layer(households, "Households", "#77827d", point=True, style={
                "radius": 2, "weight": 0.5, "fillOpacity": 0.45,
            }).add_to(group)
            group.add_to(map_view)

    def _splitters(self, owner, group):
        popup = (
            "id", "partner", "status", "lat", "lon", "offset_m",
            "road_id", "patch", "flags",
        )
        normal, review = [], []
        for point in self.points_by_owner[owner]:
            row = feature(
                {"type": "Point", "coordinates": [point["lon"], point["lat"]]},
                display_properties(point),
            )
            (review if needs_review(point) else normal).append(row)
        for label, rows, style in (
            ("Network splitters", normal, {"radius": 4.5, "weight": 1}),
            ("Network splitters needing review", review,
             {"radius": 5, "color": "#1f2937", "weight": 2.5}),
        ):
            if rows:
                spatial_layer(rows, label, provider_colour(owner), popup, True,
                              style).add_to(group)

    def _routes(self, owner, group):
        routes = [feature(
            {"type": "LineString", "coordinates": link["coordinates"]},
            display_properties({key: value for key, value in link.items()
                                if key != "coordinates"}),
        ) for link in self.routes_by_owner[owner]]
        if routes:
            spatial_layer(
                routes, "Same-provider road connections", provider_colour(owner),
                popup_fields=("from_splitter", "to_splitter", "partner_id", "distance_m"),
                style={"weight": 4, "opacity": 0.9},
            ).add_to(group)

    def _snaps(self, owner, group):
        """Show inferred GPS-to-road offsets so network lines meet their nodes."""
        links = []
        for point in self.points_by_owner[owner]:
            if "matched_lon" not in point:
                continue
            original = [point["lon"], point["lat"]]
            snapped = [point["matched_lon"], point["matched_lat"]]
            if original == snapped:
                continue
            links.append(feature(
                {"type": "LineString", "coordinates": [original, snapped]},
                display_properties({"id": point["id"], "description":
                                    "Estimated position-to-road snap (not a cable)"}),
            ))
        if links:
            spatial_layer(
                links, "GPS-to-road snap offsets", provider_colour(owner),
                popup_fields=("id", "description"),
                style={"weight": 1.5, "opacity": 0.65, "dashArray": "3 4"},
            ).add_to(group)
