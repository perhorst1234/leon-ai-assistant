# Rootless Podman test sandbox

This execution contract is deliberately not connected to the API. The example
configuration is disabled and has no image or commit; deployment must fill every
value before execution can proceed.

Build a dedicated Linux base image from exactly `base_commit`, with source,
locked dependencies, and test tooling baked into `/app`. Publish it only as an
immutable `repository@sha256:<64 hex>` reference. Before every test run contract
verifies local rootless Linux root-owned Podman executable and stable inode,
matching service UID/GID,
cgroup v2, seccomp, allowlisted Podman version, exact inspected image digest,
and one isolated non-root smoke run.

It runs fixed `python -I -m pytest -q --disable-warnings --maxfail=1` without a
shell. Container cannot pull, use network or inherited proxy settings, write
its root or image volumes, retain capabilities, gain privileges, use host
IPC/PID namespaces, or exceed configured process/memory/CPU/file limits. It
receives only noexec,nosuid,nodev `/tmp` tmpfs and read-only binds at
`/app/<path>`. Bind sources are descriptor-safe byte snapshots in random
service-owned `0700` staging directory; mutable workspace paths are never
bound. No home, socket, device, GPU, env-file, or caller environment enters
container. Client subprocess receives only PATH, locale, HOME and optional
XDG runtime path needed by local rootless Podman.

Target-host acceptance requires probe under intended Ubuntu service account and
known pass/failure proof. Preserve hashes plus secret-redacted bounded 64 KiB
stream samples, argv hash, unique container name, result, and cleanup evidence.
Every smoke or test run executes `podman rm --force --ignore` for exact generated
name; result cannot pass unless cleanup succeeds. Consult official Podman
[`run`](https://docs.podman.io/en/latest/markdown/podman-run.1.html),
[`info`](https://docs.podman.io/en/latest/markdown/podman-info.1.html),
[`image inspect`](https://docs.podman.io/en/latest/markdown/podman-image-inspect.1.html),
and [`rm`](https://docs.podman.io/en/latest/markdown/podman-rm.1.html)
documentation. This document makes no live deployment or API-wiring claim.
Target service account must be dedicated to Leon and must not run untrusted host
processes. That account boundary protects private staging paths from same-UID
replacement; untrusted code belongs only inside Podman isolation.
