"""WGS84 local East/North metres using ECEF/ENU (EPSG method 9837).

See https://proj.org/en/stable/operations/conversions/topocentric.html.
All vertices are restricted to a 25 km chord radius around the origin.
"""

import math


def coordinate(lat, lon) -> tuple[float | None, float | None]:
    """Validate a latitude/longitude pair at the external input boundary."""
    try:
        latitude, longitude = float(lat), float(lon)
        if (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            return latitude, longitude
    except (TypeError, ValueError):
        pass
    return None, None


class LocalMetres:
    """Project a small regional pilot into its own metric engineering plane."""

    max_radius_m = 25_000

    def __init__(self, lon, lat):
        self.lon, self.lat = lon, lat
        longitude, latitude = math.radians(lon), math.radians(lat)
        self.sl, self.cl = math.sin(longitude), math.cos(longitude)
        self.sp, self.cp = math.sin(latitude), math.cos(latitude)
        self.origin = self.ecef(lon, lat)

    @staticmethod
    def ecef(lon, lat):
        """Convert zero-altitude geodetic coordinates to geocentric metres."""
        longitude, latitude = math.radians(lon), math.radians(lat)
        eccentricity_squared = 6.6943799901413165e-3
        radius = 6378137.0 / math.sqrt(
            1 - eccentricity_squared * math.sin(latitude) ** 2
        )
        return (
            radius * math.cos(latitude) * math.cos(longitude),
            radius * math.cos(latitude) * math.sin(longitude),
            radius * (1 - eccentricity_squared) * math.sin(latitude),
        )

    def project(self, lon, lat):
        """Return East/North metres, rejecting points outside the local model."""
        x, y, z = (
            value - origin for value, origin in zip(self.ecef(lon, lat), self.origin)
        )
        # A chord check also rejects antipodal points that fold into the plane.
        if math.sqrt(x * x + y * y + z * z) > self.max_radius_m:
            raise ValueError(
                "Road analysis is limited to 25 km from the pilot centre; "
                "choose a smaller region/road file"
            )
        return (
            -self.sl * x + self.cl * y,
            -self.sp * self.cl * x - self.sp * self.sl * y + self.cp * z,
        )

    @property
    def metadata(self):
        """Describe the projection used in persisted run configuration."""
        return {
            "method": "WGS84 local topocentric East/North, metres (EPSG method 9837)",
            "origin_lon_lat": [self.lon, self.lat],
            "max_radius_m": self.max_radius_m,
            "note": (
                "Local surface distances; no altitude/cable slack allowance. "
                "Run separate regional pilots."
            ),
        }


def interpolate(start, end, fraction):
    """Interpolate coordinates without changing their coordinate system."""
    return [
        start[0] + (end[0] - start[0]) * fraction,
        start[1] + (end[1] - start[1]) * fraction,
    ]
