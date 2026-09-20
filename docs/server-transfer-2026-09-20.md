# Server transfer runbook — 20 September 2026

This runbook prepares the new motherboard and existing Linux SSD. It keeps the first boot reversible: inspect first, copy only after the target is known, and enable services last.

## Already completed in repository

- Local control plane, Gaia web dashboard, task queue, agent registry, permission
  model, approvals, audit trail, memory, read-only research and model routing are
  implemented and covered by automated tests.
- Setup, start, stop, doctor, authenticated local API, SQLite backup/restore,
  delivery smoke test and disabled systemd examples exist.
- Read-only MCP bindings are staged for Marktplaats, Vinted and AliExpress.
  Bank and PayPal candidates stay disabled. Purchase, bid, message, payment and
  account mutation remain approval-gated or unavailable.
- Google Calendar/Gmail read-only previews exist. Private credential-file
  loading and disabled Composio Planner contract exist; live OAuth consent and
  account acceptance remain undone.
- Local development validation covers backend, web contract/build and browser
  flows with temporary data. Target Ubuntu/M40 evidence remains pending.
- `scripts/leon-server-preflight` reports target-host facts without installing, mounting or changing services.

## SSD observed before physical transfer

macOS read-only inventory on 20 September detected external Crucial
`CT525MX300SSD1`, 525.1 GB, with GPT, 1.1 GB EFI partition and 524.0 GB Linux
filesystem partition. macOS did not mount or recognize that filesystem. No
mount, repair, initialization, format or write was performed. Disk identifier
such as `disk6` is temporary; identify again by model and capacity on server.

## Still needs proof on target server

- Motherboard firmware, network, storage visibility, thermals and GPU driver.
- Existing SSD boots and filesystem is healthy; do not format or auto-mount unknown disks.
- Python/Node/container runtime versions and available disk space.
- GitHub access, secrets injection and external provider consent.
- One successful doctor run, smoke run and backup/restore rehearsal on target.
- Systemd user service only after smoke passes and user explicitly opts in.

## Phase 1 — hardware and BIOS

1. Power off. Disconnect other disks during first boot when practical.
2. Install motherboard, CPU cooler, RAM, GPU and existing SSD. Check power connectors and cooling.
3. Enter BIOS. Load safe defaults, then verify UEFI boot mode, correct RAM amount, CPU temperature, fan curve, NVMe/SATA visibility and boot order.
4. Leave Secure Boot and IOMMU choices documented before changing them. Save, reboot, and stop if SSD is missing or temperature is abnormal.

## Phase 2 — boot and inspect existing SSD

1. Boot the existing Linux SSD. Do not run installers or partition tools.
2. From the Leon checkout, run:

   ```sh
   ./scripts/leon-server-preflight --repo "$PWD"
   ./scripts/leon-server-preflight --repo "$PWD" --json > /tmp/leon-preflight.json
   ```

3. Save JSON output with hardware notes. Check `read_only:true`, repo branch/HEAD, dirty state, filesystems, free space, GPU and command availability.
4. If the machine fails to boot, return to BIOS and record the exact symptom. Do not repair or clone until the source SSD is identified.

## Phase 3 — obtain current code safely

Use a separate checkout directory. Preserve any local work before pulling:

```sh
git status --short
git branch --show-current
git rev-parse HEAD
git fetch --prune origin
git switch --create codex/server-setup origin/codex/complete-leon
```

If local changes exist, stop and back them up or commit them first. Never use a hard reset during transfer. Verify the expected remote, branch and commit before setup.

## Phase 4 — setup and checks

Follow `docs/installation.md` and repository setup instructions. Inject secrets through the server's secret store or environment, never into Git. Run:

```sh
./scripts/leon-doctor
./scripts/leon-delivery-smoke
```

Resolve failures one at a time. Repeat preflight after installing approved prerequisites so before/after state is recorded.

## Phase 5 — opt-in service enablement

Keep service files disabled until doctor and smoke pass. Review command, user, working directory, environment and restart policy. Enable only after explicit approval, then check status and logs. Confirm the service cannot perform payment, messaging, account or destructive actions without fresh approval.

## Phase 6 — backup, rollback and handoff

Before enabling automation, run the repository backup command and verify the archive can be listed/restored to a temporary location. Record commit, config version, preflight JSON and service state. For rollback, stop/disable the opted-in service, switch back to the recorded commit, restore configuration from the verified backup, and rerun doctor/smoke. Keep original SSD untouched as rollback source until target passes a normal reboot.

Never clone over a disk, mount an unknown filesystem, delete the old checkout, or enable payment/account integrations as part of this runbook.
