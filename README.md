# Leon AI Assistant / Gaia

Persoonlijke AI-assistent met de bestaande Gaia-frontend en Python/SQLite-backend. Werk voert lokale broncontroles uit met checkpoints, pauze, hervatten en annuleren. Chat bewaart gesprekken en gebruikt dezelfde begrensde modelqueue, met vooraf goedgekeurde tekst, gesprekscontext en kostengrenzen. Zie [chat en verificatie](docs/chat.md) en [lokale uitvoering](docs/local-work.md). Live providers en M40-doelhardware zijn nog niet gevalideerd.

## Begin hier

- [Installeren, starten en private backups](docs/installation.md)
- [Geteste installatie- en herstelketen](docs/delivery-evidence.md)
- [Chatbrowsercontrole](docs/chat-browser-evidence.md) en [webtests/pakketscan](docs/web-validation.md)
- [Actuele status en hervatinstructies](docs/handoff.md)
- [Servercode: wat bestaat, wat getest is en wat ontbreekt](docs/server-recovery-audit.md)
- [Uitvoerbare backlog met acceptatiecriteria](docs/implementation-backlog.md)
- [Volledig productplan](docs/personal-ai-assistant-plan.md)
- [Tesla M40 / Xeon-doelhardware](docs/hardware.md)
- [Bestaande websitebroncode](apps/web)
- [Frontend starten en herkomst](apps/web/README.md)

Werk en Chat hebben een backendverbinding en een afzonderlijk ontwerpvoorbeeld. Vandaag, Memory en specialistische agents blijven demo; de voorbeelden bewijzen geen echte integraties.

GitHub bewaart code, besluiten, voortgang en hervatstappen. De repository is openbaar: credentials, persoonlijke gesprekken, databases, betaalgegevens en serverback-ups horen in een aparte private back-up. Een Git-push is geen back-up van de volledige server of van lopende agentprocessen.
