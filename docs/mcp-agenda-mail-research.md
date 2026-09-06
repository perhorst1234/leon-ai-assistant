# MCP agenda/mail research

Status: review-only research  
Datum: 2026-08-01  
Scope: GitHub/MCP kandidaten uit `docs/personal-ai-assistant-plan.md`, zonder install, clone, OAuth, accountkoppeling of secrets.

## Uitkomst

Voor Leon is de juiste volgorde:

1. Calendar/read-only planner PoC bouwen met previews.
2. Pas daarna Gmail/mail lezen en drafts.
3. Live mail verzenden, kalender schrijven, RSVP, contacten/taken wijzigen en OAuth scope-uitbreiding blijven approval-gated.

Geen onderzochte kandidaat is vandaag goedgekeurd voor runtime. Ze zijn alleen toegevoegd als candidate manifests.

## Kandidaten

| Kandidaat | Bron | Eerste besluit | Waarom |
| --- | --- | --- | --- |
| Google Workspace MCP | https://github.com/taylorwilsdon/google_workspace_mcp | `sandbox_before_decision` | Hoogste hergebruikwaarde voor Gmail/Calendar/Tasks/Workspace, actief en MIT, maar zeer brede 120+ tool surface met mail/calendar/Drive writes. |
| Calendar & Email MCP Server | https://github.com/MarimerLLC/calendar-mcp | `sandbox_before_decision` | Goede fit voor plannerlaag en multi-provider agenda/mail. Kleiner project; wel duidelijke tools, OAuth/config/security docs en write-tools. |
| email-mcp | https://github.com/codefuturist/email-mcp | `hold_for_later_phase` | Mail-only, read-only mode aanwezig, maar IMAP/SMTP credentials, send/manage tools en LGPL-3.0-or-later vragen aparte review. |
| Google MCP catalog | https://github.com/google/mcp | `reuse_readonly_after_review` | Officiële Google catalogus/reference. Niet behandelen als directe lokale Gmail/Calendar server. |
| Gemini CLI Workspace extension | https://github.com/gemini-cli-extensions/workspace | `sandbox_before_decision` | Door `google/mcp` genoemd als Google Workspace optie. Actief en Apache-2.0, maar README waarschuwt expliciet voor read/modify/delete Workspace access. |

## Bronbevindingen

### Google Workspace MCP

- Repo: `taylorwilsdon/google_workspace_mcp`
- Metadata op 2026-08-01: actief, niet gearchiveerd, Python, MIT, circa 2950 stars, push op 2026-07-31.
- README positioneert het als brede Workspace MCP voor Calendar, Drive, Gmail, Docs, Sheets, Slides, Forms, Tasks, Contacts en Chat.
- Repo bevat `core/tool_tiers.yaml` met Gmail-tools zoals search/get/send/draft/labels/filters en Calendar-tools zoals list/get/create.
- Repo bevat `auth/scopes.py` met Google scopes voor `calendar`, `calendar.readonly`, `calendar.events`, `gmail.readonly`, `gmail.send`, `gmail.compose`, `gmail.modify`, `gmail.labels` en andere Workspace APIs.
- `SECURITY.md` adviseert scope-minimalisatie, env vars voor gevoelige config, refresh-token rotatie en smalle file-read directories.

Conclusie: beste brede hergebruik-kandidaat, maar niet de eerste live integratie. Eerst sandbox met alleen kalender-read/free-busy en Gmail metadata/search. Write tools blijven disabled.

### Calendar & Email MCP Server

- Repo: `MarimerLLC/calendar-mcp`
- Metadata op 2026-08-01: actief, niet gearchiveerd, C#, MIT, klein maar recent, circa 19 stars, push op 2026-06-09.
- README noemt providers: Microsoft 365, Outlook.com, Google Workspace/Gmail, IMAP/SMTP, ICS feeds en JSON calendar files.
- `docs/mcp-tools.md` documenteert read tools voor mail/calendar/contacts en write tools zoals `send_email`, `create_event`, `update_event`, `delete_event`, `respond_to_event`, contacts en mail management.
- `src/CalendarMcp.Core/Constants/OAuthScopes.cs` splitst Google default scopes en read-only scopes. Read-only Google scopes zijn `gmail.readonly` en `calendar.readonly`; default scopes bevatten ook Gmail send/compose/modify en Calendar events.
- `docs/security.md` beschrijft token/config opslag, scope-minimalisatie, redacted logging en rollback via token/cache removal.

Conclusie: mogelijk beste eerste planner-sandbox als we starten met ICS/JSON/read-only Google scopes. Niet direct installeren; eerst individuele tool mapping en denied-write tests.

### email-mcp

- Repo: `codefuturist/email-mcp`
- Metadata op 2026-08-01: actief, niet gearchiveerd, TypeScript, LGPL-3.0-or-later, circa 86 stars, push op 2026-05-20.
- README noemt 47 tools voor read/search/send/manage/schedule/analyze, OAuth2 experimenteel en IMAP/SMTP config.
- `src/tools/register.ts` registreert read tools altijd, maar write tools niet wanneer `readOnly` aan staat.
- `SECURITY.md` noemt read-only mode, rate limiting, redaction en audit logging.
- Env/config surface bevat o.a. `EMAIL_ACCOUNTS`, `MCP_EMAIL_USERNAME`, `MCP_EMAIL_PASSWORD`, `MCP_EMAIL_IMAP_HOST`, `MCP_EMAIL_SMTP_HOST`.

Conclusie: nuttig als mail-only fallback, maar niet eerste keuze. Directe mailboxcredentials en send/manage-tools maken dit high-risk. Licentie eerst apart beoordelen voordat code wordt geïntegreerd of aangepast.

### Google MCP catalog

- Repo: `google/mcp`
- Metadata op 2026-08-01: actief, niet gearchiveerd, Apache-2.0, circa 4456 stars, push op 2026-07-29.
- README zegt dat de repo een lijst met Google MCP servers, deployment guidance en voorbeelden bevat.
- Voor Workspace verwijst de README naar `gemini-cli-extensions/workspace`.
- README-disclaimer: niet officieel ondersteund Google-product en bedoeld voor demonstratie.

Conclusie: gebruiken als officiële discovery/reference, niet als runtime server.

### Gemini CLI Workspace extension

- Repo: `gemini-cli-extensions/workspace`
- Metadata op 2026-08-01: actief, niet gearchiveerd, TypeScript, Apache-2.0, circa 626 stars, push op 2026-07-30.
- README noemt documenten, spreadsheets, presentaties, e-mails, chat en calendar events.
- README beschrijft headless OAuth login en zegt dat codes via `/dev/tty` worden gelezen en niet aan het AI-model worden blootgesteld.
- README waarschuwt dat deze MCP-server de agent toegang geeft om Workspace-data te lezen, wijzigen en verwijderen.
- Services bevatten Gmail search/get/modify/send/draft en Calendar list/create/update/delete/respond-achtige flows.

Conclusie: serieus alternatief omdat het via Google’s MCP catalogus wordt genoemd, maar high-risk. Alleen sandbox na scope-map, read-only config en denied-write tests.

## Manifest updates

Toegevoegd aan `config/tool-catalog.candidates.json` en de lokale dashboardstore:

- `google-workspace-mcp-candidate`
- `calendar-email-mcp-candidate`
- `email-mcp-candidate`
- `google-mcp-catalog-candidate`
- `gemini-workspace-extension-candidate`

Alle manifests blijven `candidate`. Er is geen approval, install, connect of runtime-enable uitgevoerd.

## Approval gates

Altijd approval-gated:

- package/repo/MCP installeren;
- Google/Gmail/Microsoft/IMAP/SMTP account koppelen;
- OAuth client/secret/token toevoegen of scope uitbreiden;
- Gmail/mail verzenden, reply, forward, scheduled send;
- mail verwijderen, archiveren, verplaatsen, labelen als dat externe mailbox-state wijzigt;
- kalender event aanmaken, wijzigen, verwijderen;
- RSVP/decline/accept of uitnodigingen versturen;
- contacten/taken/Drive/Docs/Sheets wijzigen;
- bulk send, scraping, public posting, spend/resource-heavy acties.

Toegestaan zonder extra approval blijft alleen lokale read-only research/manifestwerk. Runtime read access mag pas na manifestpromotie naar `approved_readonly`.

## Eerste sandboxvoorstel

Eerste technische test later:

1. Maak een disposable sandboxworkspace zonder user-home mount.
2. Gebruik geen echte persoonlijke mailbox of hoofdcalendar.
3. Start met `Calendar & Email MCP Server` of `Google Workspace MCP` in read-only mode.
4. Test alleen:
   - list calendars;
   - read event range;
   - free/busy;
   - Gmail metadata/search zonder body tenzij expliciet gekozen;
   - conceptplanning genereren zonder write.
5. Denied tests:
   - send mail geblokkeerd;
   - create/update/delete event geblokkeerd;
   - raw secret read geblokkeerd;
   - prompt-injection in mail/calendar content mag geen tool-scope uitbreiden;
   - broad Drive/mailbox access geblokkeerd.

Pas na deze test mag een aparte approval-card worden gemaakt voor een concrete read-only accountkoppeling.
