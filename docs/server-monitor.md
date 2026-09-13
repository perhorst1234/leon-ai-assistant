# Read-only server monitor

Leon exposes `GET /api/server/status` behind the existing dashboard
authentication boundary. The endpoint is enabled by default for local use and
requires no connector credentials. It reports only bounded aggregate metadata:
OS/platform, uptime, load, memory, disk capacity for fixed Leon paths, the
current Leon process and a small health check. Disk entries expose fixed labels,
never absolute local paths.

The implementation uses Python standard-library probes and never accepts a
command, path, or query parameter from the caller. Unsupported or inaccessible
metrics return `status: "unavailable"` with a short reason. It does not read
logs, file contents, environment values, or secrets, and the endpoint accepts
GET only. Exact bearer authentication is required. The connector registry
reserves `server:status_read` and records each enabled probe as read-only
connector execution. When `LEON_SERVER_MONITOR_ENABLED=false`, Leon records a
denied/no-execution check and does not run probes.

There is no scheduler, overview polling side effect or background write.

Platform support is explicit. Linux reads `MemAvailable` from `/proc/meminfo`.
Darwin exposes total memory through `sysconf`, but this standard-library-only
slice does not invent an available-memory estimate; that field is `null` with
`status: "partial"`. Gaia renders it as `—` while still showing total memory.
