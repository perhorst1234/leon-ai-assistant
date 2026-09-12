# Leon AI Assistant / Gaia

Persoonlijke AI-assistent met de bestaande Gaia-frontend en Python/SQLite-backend. Werk voert lokale broncontroles uit met checkpoints, pauze, hervatten en annuleren. Chat bewaart gesprekken en gebruikt dezelfde begrensde modelqueue, met vooraf goedgekeurde tekst, gesprekscontext en kostengrenzen. Zie [chat en verificatie](docs/chat.md) en [lokale uitvoering](docs/local-work.md). Live providers en M40-doelhardware zijn nog niet gevalideerd.

## Begin hier

- [Installeren, starten en private backups](docs/installation.md)
- [Geteste installatie- en herstelketen](docs/delivery-evidence.md)
- [Chatbrowsercontrole](docs/chat-browser-evidence.md) en [webtests/pakketscan](docs/web-validation.md)
- [Veilige nachtvoorbereiding en ochtendbrief](docs/autonomy-browser-evidence.md)
- [Actuele status en hervatinstructies](docs/handoff.md)
- [Servercode: wat bestaat, wat getest is en wat ontbreekt](docs/server-recovery-audit.md)
- [Uitvoerbare backlog met acceptatiecriteria](docs/implementation-backlog.md)
- [Volledig productplan](docs/personal-ai-assistant-plan.md)
- [Tesla M40 / Xeon-doelhardware](docs/hardware.md)
- [Bestaande websitebroncode](apps/web)
- [Frontend starten en herkomst](apps/web/README.md)

Werk, Chat, Vandaag en Memory hebben een backendverbinding en een afzonderlijk
ontwerpvoorbeeld. Vandaag toont duurzame werk-/geheugenaantallen. Memory kan
opgeslagen context met bron zoeken, toevoegen, corrigeren en met reden
verwijderen. Zie [lokaal acceptatiebewijs](docs/memory-today-browser-evidence.md).
Specialistische agents blijven ontwerpvoorbeeld; voorbeelden bewijzen geen
externe integraties.

Google Agenda/Gmail is gekozen als eerste alleen-lezen koppeling. Begrensde
client, geauthenticeerde serverroutes en Gaia-preview zijn lokaal getest. Zie
[Google alleen-lezen](docs/google-readonly.md) en
[browseracceptatie](docs/google-browser-evidence.md). OAuth-accountverbinding en
live gegevens blijven bewust nog niet geclaimd.

Gaia toont opgeslagen nachtvoorbereiding en ochtendbrief. Veilige lokale
bronscan kan handmatig of via optionele Ubuntu-timer om 22:00 draaien, zonder
provider- of netwerkverzoek. Gaia heeft ook een begrensde Firecrawl search-only
Research-flow met duurzame previewbinding en bronallowlist, standaard uit. Zie
[researchconfiguratie](docs/research-executor.md) en
[browserbewijs](docs/research-browser-evidence.md). Live provideracceptatie en
self-improvement blijven open.

GitHub bewaart code, besluiten, voortgang en hervatstappen. De repository is openbaar: credentials, persoonlijke gesprekken, databases, betaalgegevens en serverback-ups horen in een aparte private back-up. Een Git-push is geen back-up van de volledige server of van lopende agentprocessen.
