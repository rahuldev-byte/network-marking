"""CSV exports with one shared spreadsheet text-escaping policy."""

import csv

REVIEW_COLUMNS = (
    "splitter_id", "partner_id", "latitude", "longitude", "status",
    "road_offset_m", "road_id", "patch_id", "review_flags",
)


def spreadsheet_safe(value):
    """Keep arbitrary identifier text from being interpreted as a formula."""
    if isinstance(value, str) and (
        value.startswith(("\t", "\r", "\n"))
        or value.lstrip().startswith(("=", "+", "-", "@"))
    ):
        return "'" + value
    return value


def write_csv(path, columns, rows) -> None:
    """Write header and rows while applying escaping to every text column."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        writer.writerows(
            [spreadsheet_safe(value) for value in row] for row in rows
        )


def review_csv(path, points) -> None:
    """Export original splitter locations plus derived review fields."""
    rows = (
        [
            point.id, point.partner, point.lat, point.lon, point.status,
            round(point.offset_m, 4) if point.offset_m is not None else "",
            point.road_id, point.patch, ";".join(point.flags),
        ]
        for point in points
    )
    write_csv(path, REVIEW_COLUMNS, rows)


def write_records(path, rows: list[dict]) -> None:
    """Write an ordered record table using the same escaping as review CSVs."""
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    columns = list(rows[0])
    write_csv(path, columns, ([row[key] for key in columns] for row in rows))
