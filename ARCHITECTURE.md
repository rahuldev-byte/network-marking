# How the mapper is organized

Read this alongside [README.md](README.md). The README explains how to view outputs and run the tool; this document explains where to change its behavior.

The package uses composition: input readers produce domain records, a road-analysis service computes results, and output adapters serialize those results. CLI parsing, network access, business rules, metrics and browser rendering have separate owners. Small stateless geometry and formatting operations remain functions.

## Follow one run

```text
cspmap run --config pilot.toml (or python -m cspmap run ...)
  → command_config optionally expands TOML settings and CLI overrides
  → cli.CommandLine validates the resulting options
  → workflows.MappingApplication loads and profiles CSV inputs
  → ProfileWorkflow writes a point overview
    OR RegionalWorkflow selects the pilot and loads roads
       → analysis.RoadAnalysis
          → matching.RoadMatcher accepts clear road anchors
          → graph.augmented_graph splits edges at those anchors
          → routing.ConnectionFinder finds successive same-owner routes
          → patches.PatchBuilder forms groups for each threshold
       → run_output.RegionalOutputWriter writes the result snapshot
```

`python -m cspmap.metrics` loads a completed result through `SavedRun`. `ParameterEvaluator` calls the same `RoadAnalysis` service and reuses one projected GeoDataFrame/spatial index across matching-parameter evaluations. The index belongs to that loaded road snapshot, not a global cache. It does not maintain a separate copy of the routing algorithm.

`RoadAnalysis` copies source points and flags before matching; its caller's records stay unchanged. Each threshold gets its own point snapshot. The workflow explicitly exports the selected result's points, so CSVs, GeoJSON and maps are independent of threshold evaluation order. Lower-level matching and patch functions still mutate their supplied points. Graph, match and connection structures shared between threshold results must be treated as read-only.

`SnapshotValidator` compares the replay with saved counts, point states, exact patch membership, connection identities, route distances and coordinates before metrics sweeps begin. Undirected routes may be reversed, and comparisons allow numeric noise and the four-decimal precision of exported offsets. Equal counts alone are insufficient evidence of reproducibility. This checks consistency with saved results, not their real-world correctness or authenticity.

## Responsibility map

| Area | Files and their specific responsibilities |
| --- | --- |
| Command boundary | `__main__.py`: module entry point. `command_config.py`: optional TOML inputs, path resolution and explicit-flag precedence. `cli.py`: argument groups, CLI validation and terminal errors. `configuration.py`: typed regional settings and the persisted config schema. |
| Domain records | `models.py`: Point, Segment, Match, typed connection/patch records and named RoadGraph fields. |
| Source preparation | `csv_input.py`: pandas CSV parsing, WGS84 GeoDataFrames, null invalid geometries and adaptation into domain records. `regions.py`: bounds and deterministic pilot selection. `quality.py`: derived source flags and quality counts. |
| Workflows | `workflows.py`: load inputs and coordinate profile/regional stages. `summary.py`: regional/provider counts. |
| Road input | `road_validation.py`: node/coordinate boundary checks. `road_network.py`: validated graph storage. `road_loaders.py`: company vector/GeoJSON and Overpass adapters, retaining explicit topology. `road_download.py`: injectable Overpass client. |
| Geometry | `projections.py`: recorded local metric CRS, GeoPandas transformations, radius guards and saved-run reconstruction. `geospatial.py`: GeoDataFrame road layers and GeoJSON serialization. `geo.py`: coordinate validation, interpolation and compatibility projection for ENU snapshots. |
| Road analysis | `matching.py`: GeoPandas spatial-index candidate search, Shapely distance/linear referencing and the conservative acceptance policy. `graph.py`: partial-segment anchors. `routing.py`: bounded route search and pair deduplication. `patches.py`: union-find groups. `analysis.py`: shared pipeline and threshold snapshots. |
| Result output | `serialization.py`: JSON/GeoJSON primitives. `tabular_output.py`: shared CSV escaping and tables. `spatial_output.py`: spatial layers. `map_output.py`: report payloads and Folium rendering delegation. `run_output.py`: complete regional export. |
| Human reports | `markdown.py`: tables, number display and identifier escaping. `report.py`: regional review. `metric_rows.py`: metric table rows. `metrics_report.py`: metric report sections. |
| Metric evaluation | `saved_run.py`: read saved exports and recreate independent point records. `snapshot_validation.py`: compare replayed records and routes with the saved baseline. `sensitivity.py`: parameter sweeps with one reusable road index. `statistics.py`: distributions and partition agreement. `provider_metrics.py`: provider measurements. `road_statistics.py`: topology/geometry diagnostics. `measurements.py`: matching, connectivity and source-quality measurements. `metric_service.py`: assemble the final metrics document. `metrics.py`: CLI and compatibility entry points. |
| Browser map | `folium_map.py`: compose a Folium/Leaflet report and plugins. `map_layers.py`: GeoDataFrame-backed layers, popups and provider grouping. `map_controls.py`: provider filter control. `web/provider_filter.js`: one provider-selection policy that hides/shows its combined network sublayer (routes, snap offsets and nodes) together. |

The old `data.py`, `roads.py` and `output.py` imports remain as explicit compatibility APIs. They re-export their implementations, so existing callers keep working without maintaining two implementations. New internal code imports the owning module directly.

The optional TOML command file is an input convenience, separate from generated `config.json`. `CommandConfig` translates known, typed fields into CLI arguments; `CommandLine` remains the owner of required options, mutually exclusive choices and distance validation. An explicit region/source flag replaces the corresponding file choice. The OSM Overpass source is the fallback when no source flag is given; `--roads` and `--points-only` override it. File paths resolve relative to the TOML directory, while explicit CLI paths retain normal working-directory semantics. No distance (`x_m`) business threshold is supplied implicitly.

## Rules to preserve when changing code

- Ownership comes from the source ID, never from proximity. Households remain neutral without an authoritative ownership relationship.
- A screen crossing does not establish a road junction. Explicit node identity does.
- Matching considers only candidates within tolerance and rejects competing non-equivalent anchors within the ambiguity margin.
- Routing starts at accepted positions partway along segments. Point-to-road offsets do not count toward the strict `distance < x` rule.
- Another provider does not block physical traversal. A search branch stops at the next splitter of the source provider; long connected chains remain possible.
- Unresolved splitters are excluded from patches. Existing output folders are preserved.
- Reports embed result data and need regeneration after source changes. Folium loads its default browser assets from CDNs; fully offline viewing requires bundling those assets. Existing snapshots do not automatically change.

## Make a focused change

| Desired change | Start here | Evidence to check |
| --- | --- | --- |
| New company road schema | Add/adapt a reader in `road_loaders.py`; use `Roads.add` for validation | Known junctions, disconnected crossings, intermediate nodes, malformed inputs |
| Different matching rule | `RoadMatcher`, especially `_ranked_candidates` and `_match_one` | Ties, equivalent junction anchors, tolerance boundary, rematching |
| Different connection rule | `BoundedRouteSearch` and `PatchBuilder` | Strict thresholds, other-owner traversal, disconnected roads, chains |
| New metric | The owning measurements module and `MetricsService` | Hand-calculated population/denominator, empty cases, replay |
| New map option or layer | Folium controls in `folium_map.py`, geometry layers in `map_layers.py`, domain selection in `map_controls.py` / `web/provider_filter.js` | Report-contract checks, provider-selection checks and a newly generated browser report |
| New export field | `models.py` and the relevant output adapter | Consumers, map payload, CSV escaping and saved-run replay |

## Verification and style

```bash
python -m unittest discover -s tests -v
gjs tests/map_smoke.js
```

The GJS checks execute the application-owned provider selection against layer doubles; Folium report-contract tests run in Python. Neither performs a visual browser review. GJS is a development tool, not a runtime dependency of the Python mapper.

`tests/test_command_config.py` covers relative paths, explicit overrides, validation and an output-producing command. `tests/test_map_output.py` covers unified filterable provider networks, one marker per splitter, link geometry and snap offset presentation, retained popups, default OSM tiles and household-only fallback. These checks protect the simpler interface without changing analysis semantics.

`pyproject.toml` configures Ruff for Python 3.11, an 88-character project line limit, import sorting, PEP 8 checks and Python errors. With Ruff installed in your development environment:

```bash
ruff check cspmap tests examples
ruff format --check cspmap tests examples
```

Use small classes when they own state or a policy, and functions for stateless calculations. Add an adapter or helper for a real responsibility rather than creating inheritance layers or a class for every function. Keep I/O at the boundaries so the routing/matching rules can be tested without a network or browser.

The flat package is grouped by responsibility in the table above. Compatibility modules only re-export old APIs. Splitting these small owners into more packages or adding a generic repository/service hierarchy would add navigation and interfaces without an identified consumer. Revisit that choice if independently reusable subsystems emerge. Module size alone does not establish good design; review dependencies, state ownership and testable business rules as well.

## GIS and map-library boundaries

`CsvPointReader.read_frame` returns an EPSG:4326 GeoDataFrame, with null geometry for invalid coordinate pairs and string ownership identifiers. Its domain adapter retains invalid records for review rather than dropping them. Road segments become a GeoDataFrame in a recorded metric CRS; `sindex` finds candidates, and Shapely computes exact candidate offsets and positions along the line. The index does not establish ownership or join crossing roads.

`MetricProjection` defines a local azimuthal-equidistant CRS and uses GeoPandas `to_crs` for geometry layers. New configs store its full CRS. `projection_from_metadata` reconstructs that CRS for replay and recognizes earlier ENU metadata without silently changing its distance model. CRS migrations can change measured distances, so compare a newly generated run rather than relabelling an older result.

Folium uses Leaflet in a normal browser. It supplies map rendering, layer controls, popups, fullscreen and measurement tools without a notebook or a live Python kernel. The provider filter is application policy: it keeps points, routes and offsets synchronized and closes stale popups. Reading a popup or using a measurement tool does not perform a new Python analysis. [Folium's HTML export documentation](https://python-visualization.github.io/folium/latest/getting_started.html) describes this report workflow.

`ResultLayers` places all inferred road-routed connections, dashed GPS-to-road offsets and splitter nodes in one visible **Provider network · nodes and links** overlay, with one filterable subgroup per provider. Each splitter has exactly one marker; matching and review status only change its style, not its layer assignment. Review points have a dark outline. The raw road graph and OSM tile basemap are visible behind the network, while owner-unknown household points are an optional, hidden reference layer. The provider selector hides/shows each provider’s links and nodes together. The layer menu, provider search and explanation panel start collapsed. Original coordinates remain in popups. `write_map_snapshot` regenerates the viewer from a saved payload without recalculating or manufacturing connections.

### Renderer choice and remaining limits

| Option | Fit for this application |
| --- | --- |
| Direct Folium | Combined region-level network visualizations, OSM road geometry, linked provider subgroups and source-popups. It is the selected renderer. |
| GeoPandas `explore` | Convenient for quick maps; it also uses Folium. Explicit layer composition is clearer here for linked provider filtering. |
| Leafmap | Useful when its additional GIS tools or multiple backends are required. Its Folium backend uses the same renderer; backend capabilities differ. |
| Pydeck/deck.gl | A candidate for a future GPU-rendered viewer with much larger point populations. Benchmark loading, filters, memory and browser support against representative data before migrating. |

These are choices based on the current requirements, not comparative benchmarks. See the official [GeoPandas explore API](https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoDataFrame.explore.html), [Leafmap backend overview](https://leafmap.org/get-started/), [Pydeck HTML export API](https://deckgl.readthedocs.io/en/latest/deck.html) and [deck.gl performance guidance](https://deck.gl/docs/developer-guide/performance).

Large full-source HTML maps remain a scaling limitation: every exported feature is loaded in the browser. Regional selection is the supported road-analysis workflow; no national-scale browser performance is promised. A larger viewer may need aggregation, tiled data or a GPU renderer. CDN-free distribution, visual browser automation and independently labelled accuracy evaluation are also separate work. Failed runs can leave partial outputs; the tool preserves existing directories but does not provide transactional publication.
