# Project walkthrough

Use this reading order to understand one run without tracing every import.

1. Start at `src/bikepulse/pipeline.py`. `run_pipeline` is the five-step story: ingest, stage, load, validate, export.
2. Open `src/bikepulse/ingestion.py`. Notice how a run ID creates an immutable raw partition and how the checksum manifest records provenance. `http.py` contains the bounded retry behavior.
3. Read `src/bikepulse/transform.py`. This is the schema boundary: nested GBFS and weather fields become three narrow CSV tables, each carrying the run ID.
4. Read `sql/schema.sql` beside `src/bikepulse/warehouse.py`. The SQL defines the model; Python owns the transaction and replay semantics. A repeated run deletes and reinserts its facts rather than duplicating them.
5. Read `src/bikepulse/quality.py`. Each check is a small SQL assertion with an observed value and a human-readable expectation.
6. Finish with `src/bikepulse/analytics.py` and `sql/analytical_queries.sql`. These answer why the pipeline exists: a current attention queue and, once history accumulates, persistent constraint analysis.

## Follow a row

A station begins as a nested object in `station_status.json`. Its raw file is tied to a run by `manifest.json`. The transformer writes its counts to `station_status.csv`. The loader inserts it into `core.fact_station_status` with the composite key `(run_id, station_id)`. The `marts.station_health` view joins its station name and same-run weather, then assigns an operational category. The exporter writes constrained rows to `outputs/stations_needing_attention.csv`.

## Useful experiments

- Run `local-demo` twice and query `audit.pipeline_runs`: there is still one record for that run ID.
- Change one staged bike count to `-1`, reload, and run the quality function to see the contract fail.
- Run live snapshots under different IDs and execute the third analytical query after at least three captures.

