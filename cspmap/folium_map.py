"""Browser-based result maps rendered by Folium/Leaflet without a notebook."""

from html import escape

import folium
from branca.element import Element
from folium.plugins import Fullscreen, MeasureControl

from .map_controls import ProviderControl
from .map_layers import ResultLayers


class FoliumMapRenderer:
    """Compose library layers and controls from an already-computed snapshot."""

    def build(self, data):
        west, south, east, north = data["bbox"]
        map_view = folium.Map(
            location=[(south + north) / 2, (west + east) / 2],
            tiles=None, prefer_canvas=True, control_scale=True,
        )
        folium.TileLayer("OpenStreetMap", show=True).add_to(map_view)
        owners, entries = ResultLayers(data).add_to(map_view)
        folium.LayerControl(collapsed=True).add_to(map_view)
        Fullscreen().add_to(map_view)
        MeasureControl(primary_length_unit="meters").add_to(map_view)
        ProviderControl(owners, entries).add_to(map_view)
        map_view.fit_bounds([[south, west], [north, east]], max_zoom=19)
        self._summary(map_view, data)
        return map_view

    @staticmethod
    def _summary(map_view, data):
        if data["road_status"] == "available":
            description = (
                f"Route gap &lt; {data['x_m']} m · snap {data['snap_m']} m · "
                f"{data['patch_count']} groups · {len(data['connections'])} connections"
            )
        else:
            description = "Points only · road connectivity has not been calculated"
        attribution = "Road data © OpenStreetMap contributors. " if data["osm"] else ""
        road_source = "OSM" if data["osm"] else "Company"
        map_view.get_root().html.add_child(Element(
            '<details style="position:fixed;bottom:25px;left:10px;z-index:1000;'
            'background:white;padding:8px 12px;border-radius:4px;'
            'max-width:min(360px,75vw);font-size:12px">'
            '<summary style="cursor:pointer">About this map · '
            'exploratory estimates</summary>'
            f'<p><strong>{escape(data["title"])}</strong><br>'
            f'Full-region result: {description}</p>'
            '<p>Dots are splitters; lines are estimated road connections. '
            'Colour identifies the provider. Dark outlines mark splitters needing '
            'review. Solid coloured lines are same-provider routes traced on the road '
            'network. Short dashed lines show GPS-to-road snapping, not verified '
            f'cable. {road_source} road topology appears faintly behind the network. '
            'Open Layers to toggle the road graph or household reference.</p>'
            f'<small>{attribution}Exploratory estimates; household ownership is '
            'unassigned. Measurement controls do not recalculate '
            'road routes.</small></details>'
        ))
