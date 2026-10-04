# Image processor — debug console

A local, no-auth SvelteKit console for **demonstrating the backend**, not an end-user application. It shows the real reserve/upload protocol, database job states, independent generated-image requests, failures, metadata and wire responses.

Built with **Svelte 5, SvelteKit 2, TypeScript, TanStack Svelte Query and pnpm**. SvelteKit 2 / Vite 7 / adapter-node 5 are pinned deliberately rather than using the newly released SvelteKit major. No frontend service was added to Compose.

## Run

Prerequisites: Node **22.12+** (24 or 26 recommended), pnpm **12.8.1** or Corepack, and the backend API/worker/database/broker.

The instructions below are for a future run, not checks executed in this iteration. Set `DEBUG=true` in the backend `.env` before starting/recreating the API. DEBUG=false means `/debug/*` returns 404 and is omitted from OpenAPI; DEBUG is startup configuration, not authentication.

The console displays PostgreSQL status and image metadata, **not diagnostic logs**. Inspect logs separately with a Loki client or its loopback query API. There is no log endpoint or Loki proxy in the app. See the root [observability guide](../README.md#diagnostic-logs-opentelemetry-and-loki) for the minimal logging setup and limitations.

From the repository root, rebuild/start the backend services only after separately addressing any database revision issue:

```sh
docker compose -f compose.app.yaml up --build -d
```

This uses your existing backend `.env`; telemetry is enabled by default in application Compose, independently of DEBUG. **API startup runs `alembic upgrade head`.** The user removed the processing-error migration; there is no replacement or rollback migration in this change. A database still referencing that deleted revision may fail startup and needs separate user-directed reconciliation. Do not automatically reset, stamp, or drop it. Application-model cleanup does not remove leftover columns or historical values, and the live database has not been inspected. For host-run API/worker processes, set `TELEMETRY_ENABLED=true`; the OTLP endpoint already defaults to loopback. Infrastructure Compose cannot configure external Python processes.

Then, in this directory:

```sh
corepack pnpm install
cp .env.example .env
corepack pnpm dev
```

Open **http://127.0.0.1:5173**. If you already have pnpm installed, omit `corepack` in the commands. The lockfile and package-manager version are checked in. The only dependency install script explicitly allowed is esbuild.

The console proxies `/api/*` to `BACKEND_URL` (default `http://127.0.0.1:8000`). No CORS changes are needed. Set this to the address reachable **from the SvelteKit server**, not the browser. It must be a bare HTTP(S) origin with no path or credentials. Browser-facing docs/RabbitMQ links are separately configurable using the `PUBLIC_*` variables in `.env.example`.

### Production-style local run

```sh
corepack pnpm build
corepack pnpm start
```

Open **http://127.0.0.1:3000**. The start script loads `.env`, defaults to loopback and permits uploads up to 50 MiB through adapter-node. Change `PORT`, `ORIGIN`, and `BODY_SIZE_LIMIT` together as needed. The fixed upstream request timeout is 30 seconds (including streaming); large/slow transfers can time out. Do not expose this no-auth debug surface to the internet.

### Persistence

The frontend has **no database**. PostgreSQL records and image bytes remain in the existing backend's `postgres_data` and `image_data` named volumes; Loki diagnostic logs use the separate `loki_data` volume; retention deletion is not enabled in the checked-in config, so logs can accumulate indefinitely. Frontend restarts and page reloads preserve backend data; selected local files, manual upload URLs and the request inspector are session-only. Ordinary `docker compose down` keeps volumes. **`down -v` destroys database, image, broker, and diagnostic volumes**, not just logs; do not use it as a troubleshooting shortcut. Deliberate deletion of only the project-prefixed Loki volume permanently erases diagnostics and requires a separate operator decision. If running API/workers outside Docker, metadata/image persistence uses their configured database/storage path instead.

## What is shown

1. **Overview:** API reachability/version, all seven state counts and last successful read. Counts include generated records. `/health` is HTTP-process liveness, **not** database, RabbitMQ or worker health.
2. **Upload workbench:** drop/select multiple files; Upload all performs `POST /images/uploads` then raw-byte `PUT`. Reserve only and Send bytes expose each step. Declared filename/size can be overridden for negative tests. Each reservation creates a new record; sending again deliberately reuses the displayed URL. No mutation automatically retries.
3. **Live queue:** processing records first, queued oldest-first, plus pending/uploading/uploaded records. Each group is bounded to 20 with its total shown; use All records and state filters for paginated access to the rest. Inspect expands a full record card. This is **database state ordering**, not exact broker FIFO positions.
4. **Results:** Finished / Failed / All records, server-side totals and pagination, state and relationship filters. Each displayed original makes its own `GET /images/{id}?include_generated=true`; child lookup failures stay local to that card. Originals and outputs are side-by-side. Each has metadata, downloads and JSON. Metadata editing/deletion use the existing public endpoints.
5. **Request inspector:** newest 100 requests, status, duration and payloads. Poll/preview reads hidden by default. Binary bodies omitted; text bounded to 4 KiB. Direct browser downloads are not intercepted. Clear affects only the inspector, never backend data.

### State semantics and limits

| State | Meaning / debugging action |
| --- | --- |
| `pending_upload` | Reserved; bytes not received. Inspect expiry. Expiration is derived from the timestamp, not a separate state. |
| `uploading` | Backend claimed the reservation and is receiving bytes. No invented byte progress. Deletion returns 409. |
| `uploaded` | Bytes stored. Queue publication/state update may be incomplete; not proof that the worker will receive it. |
| `queued` | Waiting for processing according to the DB. Broker prefetch/concurrency/retries can alter execution order. |
| `processing` | Worker started. Time since creation/update is not a reliable processing duration. DB errors retry through Dramatiq; no retry counter/heartbeat API exists. |
| `failed` | Non-database processing error according to PostgreSQL. Inspect failure details separately in Loki, not this console or persisted error fields. Missing logs do not mean success. Re-upload creates a new job; there is no reprocess endpoint. |
| `finished` | Completed. Generated images are fetched separately; zero children can also mean they were deleted. |

- Fast jobs can pass through intermediate states between polls; the console does not fabricate historical transitions.
- Parent deletion keeps child files/records and clears their parent reference. Consequently, an orphan appears in the no-parent/original filter; historical lineage is not retained. Deletion does **not** cancel broker messages or running workers.
- Generated lookup is capped by the existing backend at **20 children**. This is explicitly labeled. The default processor currently creates one shuffled PNG.
- Previews stream at most **20 MiB** and only display byte-identified PNG/JPEG/WebP. Other formats, corrupted content and image decoding errors have explicit fallbacks. The editable `content_type` never authorizes SVG/HTML rendering. Download still retrieves the original bytes.
- Private debug metadata includes storage keys. Logs are separate local developer data; no application sanitization framework is provided. Custom processors must not embed secrets, upload-token URLs, SQL parameters, authorization headers, or payloads in exceptions.
- No complete event history, exact broker positions, worker heartbeat, cancellation, fake progress, or queue-administration actions are added.

### Separate log inspection

Failed cards show the database failure status and point developers to Loki for details. The API and console never query Loki; a Loki outage therefore does not affect metadata/status reads. Existing query caching and pause/visibility controls apply to metadata only. No log polling, ingestion-delay scheduler, attempt/message correlation, Grafana service, or tracing UI is added.

Logs can predate telemetry, arrive late, or be lost; absence of diagnostics never overrides PostgreSQL status. The console notices unavailable debug routes using `/debug/summary`, not per-image 404s. DEBUG and `TELEMETRY_ENABLED` are independent.

## Deferred demo / negative-test checklist

These are future exercises only. Do not execute them as part of this no-tests iteration.

- **Happy path:** upload a PNG/JPEG; watch states and the finished original/output pair. Check separate child GET requests in the inspector. Download both and compare dimensions/pixels.
- **Pending:** Reserve only, refresh/reload, and find the record under awaiting upload. Inspect its expiration timestamp.
- **Expired URL:** reserve and wait longer than `UPLOAD_URL_TTL_SECONDS` (default 300s); Send bytes returns 410. The backend removes the expired record on that attempt; later reuse may return 404.
- **Used URL:** send a successful upload again; expect 409 without automatic retry.
- **Invalid metadata:** declare a `.gif` / `.svg` filename or zero size; reservation returns 422. The frontend intentionally allows these debug requests through.
- **Byte mismatch:** declare a positive size different from the file's actual size; reserve then send. Expect 422 and backend cleanup of the reservation/temporary upload.
- **Corrupt bytes:** upload a text file renamed `.png`. Upload can succeed; the worker subsequently marks it failed. Inspect failure details separately in Loki (allowing for ingestion delay or loss) and the console's preview fallback.
- **Queued:** temporarily stop the worker, upload, then restart it. **Processing:** use a sufficiently large image; quick jobs may finish between polls. Do not interpret missing intermediate observations as skipped worker steps.
- **Edit:** change filename/content type, save, and inspect PATCH/refresh. Bytes do not change, and a claimed HTML MIME type is not rendered as HTML.
- **Delete:** read the confirmation, delete an original, then see the retained child in All records. Attempt deletion of an actively uploading record to see the backend's 409.
- **Offline:** stop the API; errors and stale-data notices remain visible. Pause polling, restart API, Refresh now, then resume.
- **Publication failure:** with a running API, make RabbitMQ unavailable and upload. The PUT can fail after bytes were stored. Inspect `uploaded` records; do not automatically resend consumed upload URLs.
- **Pagination:** create more than 20 records, navigate pages/change filters, delete the final item on the last page. The page clamps to the remaining total.

## Validation scope

Tests were intentionally skipped for this observability iteration: no test additions/edits/runs, browser tests, smoke tests, or manual end-to-end exercises. Existing suites are preserved; assertions about persisted failures or always-enabled debug routes may be stale and are not evidence for this integration. No migrations, database inspection/repair, or stack startup were performed.

For a separately scoped static/build review (these commands are not tests):

```sh
corepack pnpm check
corepack pnpm build
```

Static checking still reports an existing browser-test fixture that references removed persisted-error fields; it is preserved under the no-test-edits constraint. The production build is separate from those stale fixtures. Static/build checks and Compose rendering do not verify runtime export, SDK shutdown, Loki ingestion, DEBUG routing, or UI behavior; runtime exercises remain deferred. The original observability plan's log-reader/UI task was removed at the user's request.
