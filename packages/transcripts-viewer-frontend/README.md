# Transcripts viewer

Vue/Vite frontend and Fastify REST API for experiment artifacts. Requires Node22.12+ and pnpm.

```sh
cd packages/transcripts-viewer-backend
pnpm install
cd ../transcripts-viewer-frontend
pnpm install
pnpm exec node bin/transcripts-viewer.js /path/to/experiment
```

One command serves both on port5173 (`--port` overrides it), including duncan's
Tailscale hostname. The directory must contain `runs/`; omit it to use the current
directory. The `transcripts-viewer` bin is available when this package is linked.

All experiment data comes from live API requests backed by the Node dirsql SDK
from thekevinscott/dirsql. The backend ports the experiment database and schema
from `packages/run_database`; its viewer adaptations retain partial runs and
separate test results for each retry. SQL path tables read the additional
artifacts without embedding them in the frontend. Raw file downloads stream
the original bytes through the existing containment checks. Usage parsing is reused
only while file inode, nanosecond mtime and size are unchanged; every read checks
those disk attributes, so new usage appears without restarting.

Open views update through SSE without a manual refresh. The browser multiplexes its open resources over one `/api/events?resources=…`
connection. Each event contains a complete endpoint response, so the dashboard
appears as one table rather than rows arriving separately. The server checks
subscribed resources two seconds after each read finishes and emits only changed
snapshots. Reads never overlap for the same resource. Reconnecting receives
current snapshots. This avoids a recursive filesystem watch of the large dataset. Closed panels do not fetch their contents. No restart
or data embedding is needed. Static data export
(`--build`) has been removed; `pnpm run build` only compiles the frontend code.

API endpoints:
- `GET /api/events?resources=["/api/runs",…]`: multiplexed `resource` events containing `{url,data}` (URL-encode the JSON array).
- `GET /api/runs`: complete summaries and graph points.
- `GET /api/runs/index`: lightweight run identities for navigation.
- `GET /api/runs/:run/summary`: one run’s summary and graph points.

Direct run links subscribe only to their own summary plus the lightweight index.
The dashboard subscribes to `/api/runs` and displays the complete table response.
- `GET /api/runs/:run`: windows, forks, turns, advice, scores, sample outcomes.
- `GET /api/runs/:run/windows/:window/forks/:fork/turns/:turn/transcript`: U context.
- `GET /api/runs/:run/windows/:window/forks/:fork/turns/:turn/ts/:sample`: separate attempts, generation outcomes, test results, and file descriptors.
- `GET /api/runs/:run/files/*`: plain text file or directory listing, with traversal and symlink checks.
- `GET /api/runs/:run/problem/:file`: question.txt, input_output.json, or solutions.json.

Every data endpoint also accepts `Accept: text/event-stream`: it sends an initial
`data` event containing the normal response, then a replacement snapshot when
that response changes. Text endpoints send JSON-encoded strings. Streams send
heartbeats, and `stream-error` events report missing or temporarily invalid files;
subsequent valid writes recover automatically. Disconnecting releases the client
subscription; shutting down closes the query timers and SQL connections. No experiment files are modified.

U transcripts load when opened. T attempts load when their sample opens; their
transcripts and written files load when opened. File icons open a full-screen modal over the current view. Closing it preserves
scroll and disclosure state. Direct `#files/{encoded-relative-path}?src={API-URL}`
links remain supported.
A shared file matcher displays messages.jsonl as message blocks with a numbered
navigation rail, other JSONL as records, JSON as a collapsible JSON tree, and
solutions.json as one preformatted block per solution. Text files remain plain
text. The Raw view control shows the exact file text in the same viewer. Original files remain unchanged.

U context follows the runner's restore semantics: systems replace the active
system prompt, reset user records clear earlier conversation, and incomplete
replies are excluded from sent context. Advice is the saved `u/advice.txt`;
reasoning remains in its U record. Scores use recorded scorer tokens and tests.

PrimeVue supplies DataTable, Tabs, Panel, Popover, Dialog, and Select. Transcript
expansion is local to its fork; shared row heights and column resize are kept.
Separate # icons beside window/fork/turn titles and Best advice provide deep links.

Run `pnpm test` in each package. Backend tests cover readers, live API behavior,
lazy response shapes, context restoration, attempts, file containment, SSE updates
for every endpoint, missing-file recovery, and the copied database schema.
Frontend tests cover shared connection lifecycle, reconnects and cancellation.
