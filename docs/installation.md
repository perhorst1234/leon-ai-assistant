# Local installation

Leon runs as three local processes: the Python control plane, its durable
worker, and the web app. Python 3.12 or newer and Node.js 22.13 or newer are
required. The setup command creates only missing private directories and
dependencies; it does not replace an existing `.venv` or `node_modules`.

From the repository root on Ubuntu:

```bash
./scripts/leon-setup
./scripts/leon-doctor
./scripts/leon-start
# later
./scripts/leon-stop
```

`setup` creates `.env.local` with a random dashboard token if it is absent. The
file is a literal environment file, mode 600, and is read by Leon without
being sourced or executed by a shell. Keep it private. The default database is
`.runtime/control-plane.sqlite`, also private and gitignored. Set
`LEON_RUNTIME_DIR`, `LEON_ENV_FILE`, `LEON_DB_PATH`, `LEON_DASHBOARD_PORT`, or
`LEON_WEB_PORT` in the process environment to relocate delivery state or ports;
the backend and worker receive the same resolved database path.

`doctor` reports dependency, environment syntax, authentication, dependency,
and process state. A stopped service is reported as stopped, never as healthy.
It returns nonzero for missing requirements. No model is enabled by setup and
no paid provider call is made.

Create a consistent private SQLite backup with an explicit destination:

```bash
./scripts/leon-backup .runtime/backups/control-plane.sqlite
./scripts/leon-restore .runtime/backups/control-plane.sqlite
```

Both commands refuse to overwrite an existing destination by default. Use
`--force` only when that replacement is intentional. Backup uses SQLite's
online backup API and checks integrity before publishing the file. Stop Leon
before restoring so no process keeps the old database open.

The files under `deploy/systemd/` are examples for Ubuntu user services. They
bind to `127.0.0.1`, have bounded restart behavior, and are never installed or
enabled by setup.
