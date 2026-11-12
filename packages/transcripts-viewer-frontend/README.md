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

All experiment data comes from live API requests. Refresh runs or revisit the
dashboard to update summaries. Reopen panels to read changed transcripts,
attempts, and files. No restart or data embedding is needed. Static data export
(`--build`) has been removed; `pnpm run build` only compiles the frontend code.

API endpoints:
- `GET /api/runs`: complete summaries and graph points.
- `GET /api/runs/index`: lightweight run identities for navigation.
- `GET /api/runs/:run/summary`: one run’s summary and graph points.

Direct run links load only their own summary. The dashboard makes one request
to `/api/runs` and displays the complete table when that response arrives.
- `GET /api/runs/:run`: windows, forks, turns, advice, scores, sample outcomes.
- `GET /api/runs/:run/windows/:window/forks/:fork/turns/:turn/transcript`: U context.
- `GET /api/runs/:run/windows/:window/forks/:fork/turns/:turn/ts/:sample`: separate attempts, generation outcomes, test results, and file descriptors.
- `GET /api/runs/:run/files/*`: plain text file or directory listing, with traversal and symlink checks.
- `GET /api/runs/:run/problem/:file`: question.txt, input_output.json, or solutions.json.

U transcripts load when opened. T attempts load when their sample opens; their
transcripts and written files load when opened. File icons open a new tab at `#files/{encoded-relative-path}?src={API-URL}`.
A shared file matcher displays messages.jsonl as message blocks with a numbered
navigation rail, other JSONL as records, JSON as a collapsible JSON tree, and
solutions.json as one preformatted block per solution. Text files remain plain
text. File pages retain an Open raw file link. Original files remain unchanged.

U context follows the runner's restore semantics: systems replace the active
system prompt, reset user records clear earlier conversation, and incomplete
replies are excluded from sent context. Advice is the saved `u/advice.txt`;
reasoning remains in its U record. Scores use recorded scorer tokens and tests.

PrimeVue supplies DataTable, Tabs, Panel, Popover, and Select. Transcript
expansion is local to its fork; shared row heights and column resize are kept.
Separate # icons beside window/fork/turn titles and Best advice provide deep links.

Run `pnpm test` in each package. Backend tests cover readers, live API behavior,
lazy response shapes, context restoration, attempts, and file containment.
