# Werkintentie

Doel: bestaande Leon-code afmaken volgens gebruikersvisie; geen vervangende backend zonder noodzaak. Parentplan: docs/implementation-backlog.md en oorspronkelijke conceptvisie.

Baseline gelezen: AGENTS.md, README, handoff, backlog, hardware, server-recovery-audit; SSD-modules en Phase-4-PRD tijdens inventaris. Ontbrekend: actuele server/store/testfile. Architectuurreview: nodig vóór wijzigingen aan runtimecontract of autorisatie; niet nodig voor deze bronback-up/documentatie.

TaskStartSnapshot: main ed6dfb232b8aefdb29f19cdd0fb2ff8c07868e78 gelijk aan origin/main; alleen eigen eerder gemaakte docs/server-recovery-audit.md untracked, geen staged edits of actieve Git-operatie; één werkboom. Exportmappen blijven ongewijzigd.

Actieve slice: bronkopie veiligstellen, audit en hardware/uitvoeringsplan synchroniseren. Change Necessity: docs/config-only voor continuïteit; geen businesscodewijziging. TDD Mode: off / Decision: skipped voor deze kopie/documentatieslice; bestaande evaluaties wel uitgevoerd. Bij codewijziging nieuw testbesluit.

Grenzen: geen secrets/logs/DB openbaar, geen betaalde calls, geen schijfherstel, geen oude code als actuele herstelversie. Nieuwe herstelbranch is bewust geïsoleerd wegens onvolledige backend. Complexiteit: 73 bestaande files kopiëren, twee docsanitisaties, geen extra runtimeverantwoordelijkheid.

Verificatie: bronhashes, credentialpatronen, diff-check, behoud plansecties 1–24 en remote-tree/commitcontrole. Volledige release blijft needs-verification totdat ontbrekende files, hardware en live integraties getoetst zijn.
