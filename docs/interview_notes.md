# Interview notes

## The 30-second explanation

BikePulse is a local-first data platform that captures live Citi Bike station inventory and weather. It keeps immutable raw evidence, normalizes the APIs, loads a dimensional DuckDB model safely, checks every run, and publishes a station attention queue. I chose a small embedded warehouse because the data volume does not justify distributed infrastructure, but I still implemented the reliability properties that matter: lineage, idempotency, transactions, retries, tests, and executable data contracts.

## Architecture in plain language

The two APIs land as JSON under a run ID. A transform flattens them into station, status, and weather staging tables. An atomic warehouse transaction updates station attributes and replaces that run's facts. Quality SQL must pass before the output is published. The model separates relatively stable station attributes from time-varying observations.

## Hardest decisions

**Choosing the grain.** The key fact grain is one station in one captured run, not just one station. That preserves history and makes duplicates testable.

**Safe replay.** The same run ID must be retryable after failure. Facts and the audit row are replaced inside a transaction, while conflicting raw evidence is protected from overwrite.

**Avoiding tool inflation.** DuckDB and a CLI cover the actual workload. Airflow would be reasonable only after multiple pipelines, dependencies, schedules, backfills, and operational ownership justify its service overhead.

## Tradeoffs and limitations

- The committed sample is a moment-in-time capture, so its health counts are illustrative.
- A single weather coordinate cannot represent the whole service area.
- CSV staging prioritizes inspectability over compression.
- The station dimension uses a simple current-state upsert. A type-2 history would be useful only if capacity/name changes become analytical requirements.

## What I would change in production

Schedule frequent captures with a managed orchestrator, store immutable raw payloads in object storage, use PostgreSQL or a cloud warehouse for concurrent access, publish quality metrics to monitoring, and add alerts with ownership and runbooks. I would first measure volume, latency, and consumers rather than selecting tools by reputation.

## Likely questions and strong answers

**Why DuckDB instead of PostgreSQL?**  
The demo has a single writer and analytical reads. DuckDB offers transactions, constraints, SQL, and fast local scans with no server setup. PostgreSQL wins when multiple processes need concurrent access or an application serves the data.

**What makes it incremental?**  
Each execution adds one run partition and one set of status/weather facts. It does not rebuild prior observations. Station attributes are upserted because they may change.

**How is it idempotent?**  
The run ID is the idempotency key. Reprocessing it replaces only that run inside a transaction. Tests run the same ID twice and assert fact and audit counts remain unchanged.

**What happens halfway through a load?**  
DuckDB rolls the transaction back. The immutable raw partition remains available, so the same run can be replayed after the cause is fixed.

**Why store raw JSON?**  
It creates an audit boundary. If transformation logic changes, I can reproduce a run without calling a mutable live endpoint, and the SHA-256 manifest can verify the exact source bytes.

**Would the health rule scale?**  
The SQL is transparent and cheap. The thresholds should eventually be configurable by station demand and time of day; a model is unnecessary until enough labeled operational history exists.

