# Review-only self-improvement validation

`self_improvement_sandbox.execute_review_only` applies one approved patch only
inside a clean disposable Git repository below system temporary directory.
Approval binds exact repository, base commit, patch hash, file allowlist and
validation profile. Approval is consumed once before mutation.

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
records rollback evidence. Real unit/integration tests remain blocked until an
OS-level sandbox with network, filesystem, process and resource isolation is
available and verified on target Ubuntu host.
