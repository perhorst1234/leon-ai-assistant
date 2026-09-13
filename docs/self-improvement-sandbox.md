# Review-only self-improvement validation

Authenticated `POST /api/self-improvement/preview` accepts exactly a patch, a
sorted file allowlist and an allowlisted static validation profile. Server
copies only those existing repository files into a clean disposable Git
repository below its private system-temporary parent. It creates an R3 approval
bound to an opaque repository ID, exact base commit, patch SHA-256, file list
and validation profile. Approval and temporary repository expire after one
hour.

After a human approves that record, authenticated
`POST /api/self-improvement/run` accepts only approval ID plus exact patch. It
atomically consumes approval once, claims temporary repository once and runs
existing review-only validator. Concurrent or repeated runs cannot reuse it.
Public responses, approval bindings and rollback state contain no raw patch,
production path or temporary path. Restart discards in-memory claims; bounded
TTL sweep removes correctly marked abandoned repositories.

Current validator deliberately does **not** execute changed code. Temporary
directory containment is not process isolation. Supported checks are Git diff
validation and Python parsing with `ast.parse`; both use bounded input. Patch
targets must already exist, remain regular visible files and match every diff
header. New/deleted/renamed/copied/binary files, hidden paths, symlinks, path
traversal and secret-like patch text are rejected.
Repository attributes, Git filters, local includes and custom attribute files
are rejected before any status or diff command; global/system Git config and
attributes are disabled for every command.

Passing output remains `review_required`; no production branch or workspace is
touched. Static failure resets disposable repository to approved base and
records rollback evidence. API and sandbox tests include auth, exact binding,
expiry, concurrency, symlink/path replacement, secret rejection and cleanup
races. Scoped approval uses one conditional SQLite update so concurrent reject
or expiry cannot be resurrected. Full backend result on 13 September: **345
tests plus two subtests passed**; independent Python and security reviews found
no P1/P2 issue.

Gaia Werk has a collapsed advanced review card. Patch stays in component memory,
every edit invalidates preview and approval, and a separate unchecked checkbox
is required. See [browser evidence](self-improvement-browser-evidence.md). Real
unit/integration tests remain blocked until an
OS-level sandbox with network, filesystem, process and resource isolation is
available and verified on target Ubuntu host.
