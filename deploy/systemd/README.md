# systemd examples

These user service and timer files are bounded Ubuntu examples. Review paths and
resource policy for the target host, copy them to `~/.config/systemd/user/`, and
start them explicitly if desired. The source-scan timer runs daily at 22:00 in
`Europe/Amsterdam` and uses `Persistent=true` to catch up after downtime. It
indexes local source references and writes a bounded run/ochtendbrief record;
it does not run the broader mutating night queue.

```sh
systemctl --user daemon-reload
systemctl --user enable --now leon-autonomy.timer
```

The autonomy service performs only a read-only local source scan and persists
the resulting run and morning brief. It does not run the full night queue.
The repository does not install or enable services automatically; all processes
bind to loopback.
