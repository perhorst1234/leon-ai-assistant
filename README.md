# Leon AI Assistant / Gaia

Persoonlijke AI-assistent met een Gaia-frontend en bestaande Python-servercode. De volledige serverbron is inmiddels lokaal teruggehaald via WSL; zie [herstelbewijs](docs/wsl-recovery.md). GitHub bevat nog de [gedeeltelijke bron-snapshot](https://github.com/perhorst1234/leon-ai-assistant/tree/codex/ssd-recovery-2026-09-06) en een aparte nachtqueue-reparatie. Integratie van de nieuw teruggevonden grote bestanden en volledige tests volgen; nog geen startklare releaseclaim.

## Begin hier

- [Actuele status en hervatinstructies](docs/handoff.md)
- [Servercode: wat bestaat, wat getest is en wat ontbreekt](docs/server-recovery-audit.md)
- [Uitvoerbare backlog met acceptatiecriteria](docs/implementation-backlog.md)
- [Volledig productplan](docs/personal-ai-assistant-plan.md)
- [Tesla M40 / Xeon-doelhardware](docs/hardware.md)
- [Bestaande websitebroncode](apps/web)
- [Frontend starten en herkomst](apps/web/README.md)

De frontend is een interactieve demo. Zichtbare agenttaken, voortgang, geheugen en approvals bewijzen nog geen echte backendfunctionaliteit.

GitHub bewaart code, besluiten, voortgang en hervatstappen. De repository is openbaar: credentials, persoonlijke gesprekken, databases, betaalgegevens en serverback-ups horen in een aparte private back-up. Een Git-push is geen back-up van de volledige server of van lopende agentprocessen.
