"""Buffered Overpass download with explicit response and size validation."""

import json
import math
import urllib.error
import urllib.parse
import urllib.request

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
MAX_RESPONSE_BYTES = 80_000_000


class OverpassClient:
    """Fetch one regional road snapshot; network access is injectable for tests."""

    def __init__(self, endpoint=OVERPASS_ENDPOINT, opener=None):
        self.endpoint = endpoint
        self.opener = opener or urllib.request.urlopen

    @staticmethod
    def query(bbox, padding_m):
        """Request highway ways and nodes with a metric-derived region halo."""
        west, south, east, north = bbox
        lat_pad = padding_m / 110_000
        lon_pad = padding_m / (
            110_000 * math.cos(math.radians((south + north) / 2))
        )
        return (
            '[out:json][timeout:35];way["highway"]["area"!="yes"]'
            f'({south - lat_pad},{west - lon_pad},'
            f'{north + lat_pad},{east + lon_pad});(._;>;);out body;'
        )

    def download(self, bbox, padding_m, path):
        """Save a complete JSON response or raise an actionable boundary error."""
        request = urllib.request.Request(
            self.endpoint,
            data=urllib.parse.urlencode({"data": self.query(bbox, padding_m)}).encode(),
            headers={
                "User-Agent": "cspmap-local-pilot/0.1", "Accept": "application/json"
            },
        )
        try:
            with self.opener(request, timeout=45) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
            data = self._validate_response(payload)
            path.write_text(json.dumps(data), encoding="utf-8")
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Could not download OSM roads: {exc}. Supply --roads with "
                "a local road file, or use --points-only."
            ) from exc

    @staticmethod
    def _validate_response(payload):
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError("Road response too large; choose a smaller pilot")
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("Overpass response must be a JSON object")
        if (
            data.get("remark")
            or not isinstance(data.get("elements"), list)
            or not data["elements"]
        ):
            reason = data.get("remark", "no elements")
            raise ValueError(f"Incomplete or empty Overpass result: {reason}")
        return data


def download_osm(bbox, padding_m, path, endpoint=OVERPASS_ENDPOINT):
    """Compatibility entry point for buffered regional road downloads."""
    OverpassClient(endpoint).download(bbox, padding_m, path)
