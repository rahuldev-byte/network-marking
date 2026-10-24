# CSP footprint mapper

Show a single geographic network: splitter nodes and their eligible same-provider road-routed links, over an OpenStreetMap (OSM) basemap and road graph. Household locations remain a separate, owner-unknown reference layer. The output includes an interactive map, review tables, spatial exports and descriptive metrics.

Requires **Python 3.11 or later** with GeoPandas, pandas, Shapely, pyproj and Folium. GeoPandas handles spatial data, CRS transformations and indexing; Folium/Leaflet renders browser reports. Jupyter is not required. Read [ARCHITECTURE.md](ARCHITECTURE.md) for the implementation and where to make changes.

## Install

From the repository root, create and activate an environment, then install the project and its declared dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

If you already use a Conda or micromamba environment, activate it and run the installation there instead. Use that environment's Python for every command below. To include development tools, install with `python -m pip install -e '.[dev]'`.

The examples below use `python` from that activated environment. Installation also enables the `cspmap` shortcut. If the dependencies are already installed but the shortcut is unavailable, run `python -m cspmap` from the repository root instead.

## Quick start: open the OSM network map

The project includes the two recorded point CSVs and a ready-to-run OSM pilot
configuration. **There is no synthetic-data generator or fictional road demo.**
The default road source is **OpenStreetMap via Overpass**; OSM map tiles are
also shown by default in the HTML viewer. Road analysis needs an internet
connection when downloading fresh OSM ways and junction nodes.

From the repository root, after installing:

```bash
cspmap run --config examples/pilot.toml
python -m cspmap.metrics --run outputs/osm-pilot --output outputs/osm-metrics
python -m http.server 8000 --bind 127.0.0.1
```

Open the [combined OSM network map](http://127.0.0.1:8000/outputs/osm-pilot/map.html)
from the computer running the server. It plots **roads, splitter nodes, and
qualifying routed connections together**, not as disconnected standalone plots.
The command generates `outputs/osm-pilot/map.html`, the review report and the
GeoJSON exports. Stop the web server with **Ctrl+C**.

A **pre-generated map from the bundled real OSM pilot** is also included at
[outputs/osm-network-replay/map.html](outputs/osm-network-replay/map.html).
Open it without rerunning the analysis (the map tiles/CDN scripts still load online).

A saved OSM road response is also included for **offline analysis replay** of
the bundled pilot region. Use it instead of downloading roads (choose a new
output directory):

```bash
cspmap run --config examples/pilot.toml \
  --roads outputs/pilot-code-review/osm_roads.json \
  --output outputs/osm-network-replay
```

Its viewer still needs online CDN scripts and OSM map tiles unless those assets
are bundled separately. Existing recorded results are preserved rather than
overwritten. If `outputs/osm-pilot` already exists, choose another empty output
directory with `--output outputs/another-pilot` and adjust the URLs.

**Interpretation:** coloured lines show **inferred road-routed links between
matched splitters of the same recorded provider**, not surveyed fibre/cable
segments. A splitter without a qualifying link remains an unconnected node.
The map does not connect every point merely to make the diagram look complete,
and households are not assigned a provider without evidence.

## Short commands with full control

After installation, `cspmap` is the short form of `python -m cspmap`. Save repeated settings in a TOML file. For example, create `pilot.toml` in your project root, adjusting paths and parameters for your data:

```toml
splitters = "data/splitters.csv"
households = "data/households.csv"
download_osm = true
output = "outputs/company-pilot"
auto_pilot = true
x_m = 100
snap_m = 30
ambiguity_m = 2
compare_x = [50, 200]
```

Run it, or override only what you want to change:

```bash
cspmap run --config pilot.toml
cspmap run --config pilot.toml --x-m 150 --output outputs/pilot-150
```

The values above are exploratory examples, not approved business defaults. `x_m` is still required for road analysis; only the OSM road **source** has a default. The saved run records the effective settings after overrides.

- Configuration keys use underscores corresponding to CLI flags: `snap_m` becomes `--snap-m`.
- Paths in TOML are relative to that file; paths supplied on the command line are relative to your current directory.
- Explicit flags take precedence. For example, `--bbox WEST SOUTH EAST NORTH` replaces configured `auto_pilot`, and `--roads FILE` replaces configured `download_osm`. Omitting all road flags uses OSM download automatically.
- Use `--no-compare-x` to disable configured comparisons. For a points-only run, use `--points-only --no-compare-x` and a new output directory.
- `profile --config FILE` accepts `splitters`, `households`, `output` and `map`; `--no-map` disables a configured map.
- Unknown keys, wrong value types and conflicting choices are rejected. Existing output folders are still protected.

[examples/pilot.toml](examples/pilot.toml) is another editable template. All original flags remain available; `cspmap run --help` lists them. For metrics, use `python -m cspmap.metrics --run outputs/company-pilot --output outputs/company-metrics`.

Keep `pilot.toml` and generated `config.json` distinct: the TOML file is the input you edit; `config.json` records the effective settings for a completed run. A run configuration cannot also be used for `profile`, because that command deliberately rejects road-analysis keys. Metrics read the saved run directory and do not take `--config`.

### Common changes without rewriting the command

These examples assume the `pilot.toml` above is configured for your inputs. Each example uses a separate output directory.

| Task | Command |
| --- | --- |
| Use the configured settings | `cspmap run --config pilot.toml` |
| Try a different distance | `cspmap run --config pilot.toml --x-m 150 --output outputs/pilot-150` |
| Show points without road analysis | `cspmap run --config pilot.toml --points-only --no-compare-x --output outputs/point-pilot` |
| Use another road file | `cspmap run --config pilot.toml --roads data/company.gpkg --output outputs/company-gpkg` |
| Choose a region explicitly | `cspmap run --config pilot.toml --bbox 77.26 28.66 77.28 28.68 --output outputs/selected-region` |

Replace the example bounds with your actual region. When moving a TOML file to another folder, update its relative paths too. The included `examples/pilot.toml` uses `../splitter_points.csv` and `../active_base_mobile_lat_long_time_added_20261022.csv` relative to `examples/`.

## Open maps, reports and tables

After the quick start, these URLs refer to the actual outputs:

| Output | Where to open it | What it shows |
| --- | --- | --- |
| **OSM network map** | [Open network map](http://127.0.0.1:8000/outputs/osm-pilot/map.html) | One combined provider network (nodes, inferred links and short snap connectors), on OSM roads. |
| **Pilot review** | [Read REVIEW.md](http://127.0.0.1:8000/outputs/osm-pilot/REVIEW.md) | Provider groups, threshold comparisons and cases to review. |
| **Detailed metrics** | [Read METRICS.md](http://127.0.0.1:8000/outputs/osm-metrics/METRICS.md) | Matching and connectivity measurements. |
| Splitter review table | [Download CSV](http://127.0.0.1:8000/outputs/osm-pilot/splitter_review.csv) | Matched and unresolved records. |
| Provider metrics | [Download CSV](http://127.0.0.1:8000/outputs/osm-metrics/per_csp_metrics.csv) | Per-provider measurement table. |
| Run settings | [View config.json](http://127.0.0.1:8000/outputs/osm-pilot/config.json) | Actual OSM source, region and thresholds. |
| Result summary | [View summary.json](http://127.0.0.1:8000/outputs/osm-pilot/summary.json) | Splitters, patches and inferred links. |
| Metrics JSON | [View metrics.json](http://127.0.0.1:8000/outputs/osm-metrics/metrics.json) | Full measurements and parameter sweeps. |

The default view contains **one combined “Provider network · nodes and links” overlay**:
solid, provider-coloured road-routed connections, splitter markers at their
recorded coordinates, and short **dashed** GPS-to-road snapping offsets. Dashed
offsets are analytical matching guides, **not confirmed cables**. Dark marker
outlines show records needing review; every splitter is plotted once. The
**Road graph · OSM geometry** layer and OSM tile basemap are shown beneath the
network. Thus links and endpoints stay together when selecting a provider.

Use the **Provider** menu to focus one owner or search for provider IDs.
The **Layers** menu can hide the network/road context or show the optional
**Households · owner unknown** reference layer, which starts hidden. Households
are not connected to splitters because no verified ownership or physical-link
data is supplied. Click a splitter, route or snapping line for source and
inference details. Toggle Layers or filter providers to change **visibility
only**; connectivity and exports do not recalculate in the browser.

Expand **About this map** for the legend and full-region summary. Browser
measurements, zoom and fullscreen do not modify routes. Unmatched splitters
remain visible but have no invented links; a visually disjoint component
may be a true break, incomplete road data or a threshold effect. Check
`REVIEW.md` for the difference. Invalid coordinates appear in quality reports
rather than on the map. Empty contextual layers are omitted.

Generated maps embed analysis results in HTML. Folium loads Leaflet/plugin
scripts from CDNs and the default OSM basemap requests online tiles. Fully
offline viewing needs those browser assets bundled separately. Household
phone numbers are not included in the map or spatial exports. Browsers can
show Markdown as text; use VS Code Markdown Preview (**Ctrl+Shift+V**) for
formatted reports.

### Troubleshooting the viewer

- **Connection refused:** start the local viewer from the repository root and keep its terminal running.
- **404 / file not found:** generate the output first and check the URL against the output directory selected. The included historical snapshots are not automatically updated by changes to the renderer.
- **Port 8000 is in use:** run `python -m http.server 8001 --bind 127.0.0.1` and change `8000` to `8001` in the browser address.
- **Another person cannot open the localhost link:** `127.0.0.1` refers to their computer. Screen-share the map or provide the generated HTML snapshot.
- **A blank map appears:** check that your browser can load the Leaflet/Folium CDN assets; the default report requires internet access.
- **An old result appears:** reload with **Ctrl+Shift+R** and confirm you opened the intended run directory.
- **Households or offset lines seem missing:** enable the household layer when needed. Dashed match offsets are already inside the provider network; only splitters with accepted road anchors have them.
- **No records match a provider:** clear the optional search as well as the dropdown; both filters apply together.

### Troubleshooting commands

- **`cspmap: command not found`:** activate the environment where the package was installed, or use `python -m cspmap` from the repository root.
- **`No module named geopandas` or `folium`:** the selected Python lacks the dependencies. Activate the intended environment and follow the installation steps above.
- **A TOML input file cannot be found:** check paths relative to the TOML file's directory, not the terminal directory.
- **Output directory is not empty:** keep the previous result and add `--output outputs/another-run`.
- **Unknown setting in a configuration:** use the documented underscore names, such as `x_m`; input TOML is not the generated `config.json` schema.

## Supply company data

Provide these CSV schemas. Coordinates must be geographic latitude/longitude in WGS84.

| Dataset | Required columns | Meaning |
| --- | --- | --- |
| Splitters | `partner_id`, `latitude`, `longitude` | Recorded provider ownership and splitter location. |
| Households | `lat`, `long` | Household locations, displayed without inferred provider ownership. |

Additional columns may be present but are not used to infer ownership. Each record receives a source-row ID. Those IDs remain stable only while the source CSV order stays unchanged.

By default the CLI reads the bundled `splitter_points.csv` and `active_base_mobile_lat_long_time_added_20261022.csv` from the working directory. For other data, supply `--splitters` and `--households` or use a TOML configuration. Source datasets and generated outputs may be kept outside Git even when included in a distributed archive.

Profile the inputs before road analysis:

```bash
cspmap profile \
  --splitters data/splitters.csv --households data/households.csv \
  --map --output outputs/profile
```

Then open `http://127.0.0.1:8000/outputs/profile/map.html`. The accompanying `data_quality.json`, `splitter_review.csv` and `household_review.json` identify records needing inspection.

For large input files, omit `--map` when profiling and use the regional points-only command below for interactive review. Full-source maps embed every valid point and can be slow or memory-intensive in the browser; profiling itself does not require rendering a map.

A points-only regional run is also available:

```bash
cspmap run --config pilot.toml --points-only --no-compare-x --output outputs/point-pilot
```

Open `http://127.0.0.1:8000/outputs/point-pilot/map.html`. This view has no inferred road connections.

The automatic pilot selects the densest eligible 0.02-degree splitter cell, excluding zero-coordinate records, missing ownership and unsupported latitudes. It is a small study region selected by density, not a representative random sample. Use `--bbox WEST SOUTH EAST NORTH` to choose an explicit region. Profiling still completes if no automatic pilot can be selected.

## Run with company roads

The road loader accepts WGS84 GeoJSON and company vector formats supported by GeoPandas, including GeoPackage and Shapefile. Vector files must declare their CRS; the loader transforms them to WGS84. GeoJSON declaring a different CRS is rejected: reproject it first or provide a GeoPackage with its source CRS. Every road still needs a LineString geometry and explicit topology. For GeoJSON, use this contract:

```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "properties": {
      "road_id": "road-1",
      "from_node": "junction-a",
      "to_node": "junction-b"
    },
    "geometry": {
      "type": "LineString",
      "coordinates": [[77.26, 28.66], [77.261, 28.661]]
    }
  }]
}
```

Use the same node ID where roads truly join. IDs must be nonempty strings or integers. Reusing an ID at inconsistent coordinates is rejected; different IDs at the same coordinate stay disconnected. Geometric crossings alone do not create junctions.

For intermediate junctions, provide a `node_ids` list matching **every** coordinate or split the feature at each junction. With only `from_node`/`to_node`, intermediate vertices are bends unique to that feature. GeoPackage/Shapefile attributes must supply the same topology fields. A format or CRS conversion does not create missing junction identities. Provide a regional file rather than loading an entire national road network.

After preparing the road file, edit the root-level `pilot.toml` from the short-command example, then run:

```bash
cspmap run --config pilot.toml
```

You can also supply every option explicitly without a configuration file:

```bash
cspmap run \
  --splitters data/splitters.csv --households data/households.csv \
  --roads data/roads.geojson \
  --bbox 77.26 28.66 77.28 28.68 \
  --x-m 100 --snap-m 30 --ambiguity-m 2 --compare-x 50 200 \
  --output outputs/company-pilot
```

Replace the example bounds with a region overlapping your inputs. Include surrounding roads so route searches are not cut off at the study boundary. Every loaded road vertex must be within 25 km of the region centre, and road analysis is limited to 10,000 selected splitters. Use separate regional pilots for wider coverage.

Open `http://127.0.0.1:8000/outputs/company-pilot/map.html` and read its `REVIEW.md`. The parameters above are exploratory examples that require local network review.

## Download OpenStreetMap roads

If company roads are unavailable, OSM is now the default road source. A buffered regional road graph is fetched from Overpass if `--roads` and `--points-only` are both absent. You may still select OSM explicitly:

```bash
cspmap run --config pilot.toml --download-osm --output outputs/another-osm-pilot
```

This requires internet access. The request sends the buffered bounding box, not the source records. The downloaded response is saved in the selected output directory as `osm_roads.json`; its combined network map is `map.html`.

Reuse that road snapshot without downloading again:

```bash
cspmap run --config pilot.toml --roads outputs/pilot-code-review/osm_roads.json \
  --output outputs/road-replay
```

Overpass JSON must include highway ways and all referenced nodes. Incomplete responses are rejected, and ways tagged `area=yes` are excluded. OSM XML/PBF and GraphML are not supported directly.

If a download fails with a network/DNS error, retry with internet access or use a local road file. A failed run can leave preparation files behind; preserve that directory and choose a new or empty destination for the retry.

## Calculate and interpret metrics

Run metrics against any completed road analysis:

```bash
python -m cspmap.metrics \
  --run outputs/company-pilot --output outputs/company-metrics
```

Open `outputs/company-metrics/METRICS.md` in an editor, or visit `http://127.0.0.1:8000/outputs/company-metrics/METRICS.md` with the viewer running. The command also writes `metrics.json` and `per_csp_metrics.csv`. Points-only runs cannot supply road-connectivity metrics.

The metrics command compares the configured x values, matching tolerances of 10/20/30/50 m and ambiguity margins of 0/1/2/5 m, including the run's own values. Each sweep changes only its named parameter. Adjusted Rand index measures grouping agreement on commonly matched records; Jaccard measures set overlap.

Before calculating sweeps, replay checks saved splitter states, patch memberships and connections, including their geometry and distances. It refuses a different baseline even when total counts happen to match. Keep the complete result directory together. Undefined rates are reported as `null` in JSON and `N/A` in report tables.

A road-match rate measures how many records the algorithm accepted, not how many matches are physically correct. Actual accuracy, precision, recall and F1 need independently verified labels. Offset measurements describe proximity to roads, and route lengths describe the road-based model; neither establishes surveyed cable geometry. Use the reports to select examples for local review and agree on operational parameters.

## Connection rules

A **CSP/provider** is the owner identified by `partner_id`. A **patch** is a connected group of matched splitters belonging to one provider; it can contain a single splitter.

- Recorded ownership is preserved. One provider can have several disconnected patches. Household ownership remains unassigned without an authoritative identifier relationship.
- Splitters match only when a road is within tolerance and no competing non-equivalent anchor is within the ambiguity margin. Ambiguous and unmatched records remain unresolved and are excluded from patches.
- Original point locations are retained. Point-to-road offsets do not count toward route distance.
- A qualifying same-provider connection has road-route distance **strictly less than x**, measured between accepted positions partway along segments.
- Searches stop each branch at the next same-provider splitter. Short qualifying connections can form long chains. Another provider's splitter does not block the physical road.
- Road traversal is bidirectional because vehicle one-way restrictions do not represent cable connectivity. Nearby road endings and visual crossings do not establish junctions.
- A singleton can reflect a real break, missing roads, location error or the chosen parameters. No service-area polygons or household assignments are inferred.

`--x-m` is required for road analysis and has no business default. Matching tolerance defaults to 30 m and the competing-match margin to 2 m; validate both against reviewed examples.

New runs use a local azimuthal-equidistant CRS in metres, centred on the region. GeoPandas transforms road geometry with `to_crs`, and Shapely measures distances and positions on the metric geometry. The exact CRS, origin and method are recorded in `config.json` so metrics replay uses the same projection. Earlier ENU snapshots retain a compatibility reader. The model excludes altitude and cable slack and restricts vertices to a 25 km radius. See [GeoPandas CRS transformations](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoDataFrame.to_crs.html).

## Output reference

| Generated file | Purpose |
| --- | --- |
| `map.html` | Folium/Leaflet HTML report with embedded result data and CDN-hosted map assets. |
| `REVIEW.md` | Readable matching/provider summaries, comparisons and examples. |
| `config.json` | Run source, region, projection and parameter choices. |
| `data_quality.json` | Full-source quality counts, which may exceed regional totals. |
| `summary.json` | Regional matching, provider, patch and connection counts. |
| `patches.json` | Exact member splitter IDs and owner for each patch. |
| `sensitivity.json` | Requested threshold comparisons. |
| `splitter_review.csv` | Every regional splitter, including unresolved records. |
| `splitters.geojson`, `households.geojson` | Original valid locations and relevant properties. |
| `roads.geojson` | Loaded road segments and explicit node identities. |
| `connections.geojson` | Qualifying route geometry with endpoint IDs and owner. |
| `road_matches.geojson` | Original splitter-to-accepted-anchor offsets. |
| `METRICS.md`, `metrics.json`, `per_csp_metrics.csv` | Separate metrics command outputs. |

## Development

Read [ARCHITECTURE.md](ARCHITECTURE.md) for the call sequence, component responsibilities, business invariants and change locations. The Folium renderer, spatial layer construction and provider control are in `folium_map.py`, `map_layers.py` and `map_controls.py`. The small application-owned provider-selection policy is under `cspmap/web/`; Folium/Leaflet owns drawing, panning, zooming and standard controls. Regenerate maps after changing their generation code.

Run the automated checks:

```bash
python -m unittest discover -s tests -v
gjs tests/map_smoke.js
```

GJS is needed only for JavaScript checks. The GJS check exercises provider selection across combined node/link groups with layer doubles. Python tests cover the Folium report contract. Also inspect generated maps in a browser when changing their appearance or interactions; these checks do not replace browser testing.

With Ruff installed in the development environment:

```bash
ruff check cspmap tests examples
ruff format --check cspmap tests examples
```

[pyproject.toml](pyproject.toml) configures Python 3.11 compatibility, an 88-character line limit, PEP 8 checks and import sorting. The repository root uses an explicit allowlist in `.gitignore`; add an exception when introducing a new shared root file or directory.
