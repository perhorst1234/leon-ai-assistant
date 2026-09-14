# Approval-gated self-improvement validation

Authenticated `POST /api/self-improvement/preview` accepts exactly patch, sorted
file allowlist and allowlisted static validation profile. Server copies only
those existing repository files into clean disposable Git repository below its
private system-temporary parent. It creates R3 approval bound to opaque
repository ID, exact temporary review commit, patch SHA-256, file list,
validation profile, execution mode, sandbox policy fingerprint and separate
image base commit. Approval and temporary repository expire after one hour.

After human approval, authenticated `POST /api/self-improvement/run` accepts
only approval ID plus exact patch. It atomically consumes approval once, claims
temporary repository once and runs static validator. Concurrent or repeated
runs cannot reuse it. Public responses, approval bindings and rollback state
contain no raw patch, production path or temporary path. Restart discards
in-memory claims; bounded TTL sweep removes correctly marked abandoned
repositories.

Default `static_review_only` mode never executes changed code. It checks Git
diff and optionally parses Python with `ast.parse`; both use bounded input.
Patch targets must already exist, remain regular visible files and match every
diff header. New/deleted/renamed/copied/binary files, hidden paths, symlinks,
path traversal and secret-like patch text are rejected. Repository attributes,
Git filters, local includes and custom attribute files are rejected before any
status or diff command; global/system Git config and attributes are disabled.

When deployment supplied valid enabled private Podman config before preview,
approval explicitly says changed code will execute in isolated testcontainer.
Run reloads exact config fingerprint and image base. Change, corruption or
disappearance invalidates approval and cleans temporary state. After static
success, `podman_tests` mode snapshots only approved patched files and runs
fixed pytest inside digest-pinned rootless Podman contract. Network, proxy
inheritance, writable root/image volumes, capabilities, privilege gain and host
PID/IPC are blocked; resources and output are bounded; cleanup is mandatory.
Only sanitized status and hashes become durable evidence. See
[OS sandbox contract](os-sandbox.md).

No production branch or workspace is touched. Static or sandbox failure never
becomes success. Tests cover auth, exact binding, expiry, concurrency,
symlink/path replacement, secret rejection, config tamper, output caps and
cleanup races. Scoped approval uses one conditional SQLite update so concurrent
reject or expiry cannot be resurrected. Current verification: 368 backend tests
plus two subtests, 46 webtests, typecheck, production build and lint without
errors; specialist reviews found no remaining P1/P2 issue.

Gaia Werk has collapsed advanced review card. Patch stays in component memory,
every edit invalidates preview and approval, and separate unchecked checkbox is
required. Card shows static versus Podman execution before approval and reports
whether changed code actually ran. Existing static browser evidence is in
[Gaia browser evidence](self-improvement-browser-evidence.md). Live Podman tests
remain disabled until digest-pinned image and target Ubuntu host pass acceptance;
browser evidence for enabled mode remains open.
