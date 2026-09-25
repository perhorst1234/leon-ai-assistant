# Doelserver-preflight — 25 september 2026

`./scripts/leon-server-preflight --repo . --json` is op de draaiende Ubuntu-VM
uitgevoerd. Het commando is read-only en retourneerde `schema_version: 1`,
`read_only: true`, een schone Git-tree op branch `main` en HEAD
`2358747ba49a40e0182aa7bac4e6aa122ef56b0c`.

De host rapporteerde Linux x86_64, kernel `7.0.0-31-generic`, 10 CPU-threads,
`MemTotal: 9339600 kB` en `MemAvailable: 8116872 kB`. De M40 is zichtbaar als
`Tesla M40 24GB`, met NVIDIA-driver `580.178.04` en `23040 MiB` gerapporteerd
geheugen. Systemd is actief en alle Leon-units draaien: backend, worker, web,
Ollama, Caddy, tijdelijke tunnel, publieke route-timer en autonomietimer.

De rootfilesystemmeting rapporteerde ongeveer 200 GB totaal en 30% gebruikt.
Podman en Docker zijn niet geïnstalleerd; daardoor blijft de optionele
Podman-testmodus voor self-improvement terecht uitgeschakeld. Deze meting bewijst
hostbeschikbaarheid en read-only hardware-readiness, geen geïsoleerde
containeracceptatie.

De geïsoleerde delivery-smoke is daarna opnieuw uitgevoerd met vrije tijdelijke
poorten. Die doorliep setup, gequote private dotenv, drie processen, twee
geauthenticeerde HTTP 200-checks, doctor, online backup, stop waarbij alle drie
procesgroepen verdwenen, en restore met marker- en SQLite-integriteit.
