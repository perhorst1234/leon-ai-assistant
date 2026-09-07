# Leon AI Assistant / Gaia

Persoonlijke AI-assistent met de bestaande Gaia-frontend en herstelde Python/SQLite-backend. **Echte lokale taakuitvoering is nu aan de Werk-pagina gekoppeld:** broncontrole, checkpoints, pauze, hervatten en annuleren. 185 backendtests en zeven webbridge-tests slagen. Nog geen live AI-chat, provideruitvoering of M40-releaseclaim. Zie [startinstructies en bewijs](docs/local-work.md).

## Begin hier

- [Actuele status en hervatinstructies](docs/handoff.md)
- [Servercode: wat bestaat, wat getest is en wat ontbreekt](docs/server-recovery-audit.md)
- [Uitvoerbare backlog met acceptatiecriteria](docs/implementation-backlog.md)
- [Volledig productplan](docs/personal-ai-assistant-plan.md)
- [Tesla M40 / Xeon-doelhardware](docs/hardware.md)
- [Bestaande websitebroncode](apps/web)
- [Frontend starten en herkomst](apps/web/README.md)

Werk heeft een echte lokale uitvoeringsmodus en een afzonderlijk ontwerpvoorbeeld. Vandaag, Chat, Memory en specialistische agents blijven demo; de voorbeelden bewijzen geen echte integraties.

GitHub bewaart code, besluiten, voortgang en hervatstappen. De repository is openbaar: credentials, persoonlijke gesprekken, databases, betaalgegevens en serverback-ups horen in een aparte private back-up. Een Git-push is geen back-up van de volledige server of van lopende agentprocessen.
