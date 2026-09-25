# Bestaande Gaia-frontend

Bron: Codex-taak **Maak AI-assistantwebsite prachtig**, broncommit `f5e8426` van 28 augustus 2026. De eigenaar heeft deze website op 6 september 2026 aangewezen als frontend van Leon.

Deze kopie bevat 15 bestaande bron-, configuratie-, lock- en assetbestanden. Ze zijn bij het kopiëren byte-voor-byte met SHA-256 gecontroleerd. De oorspronkelijke werkmap en publicatie zijn niet gewijzigd. De hostingconfig bevat hier een lokale placeholder in plaats van de bestaande deploymentidentiteit.

## Wat bestaat

React 19, TypeScript, Next/Vinext, Vite, Motion en Lucide. Er zijn aparte Vandaag-, Chat-, Werk- en Memory-ruimtes, een frosted navigatie, de Gaia-entiteit, agentselectie, missiestatus, checkpoints, pauzeren/hervatten, approval-previews en een self-learning-preview.

Werk heeft een echte modus met backendtaken, SQLite-checkpoints en pauze/hervatten/annuleren. Chat kan via Ollama op de lokale Tesla M40 draaien. De route `app/api/leon/route.ts` koppelt server-side aan Python. De browser logt met een zelfgekozen wachtwoord en een beveiligde sessiecookie in; de backendtoken blijft op de webserver. De oude demo staat onder Ontwerpvoorbeeld. Zie [runtime-instructies](../../docs/local-work.md) en [publieke toegang](../../docs/public-access.md).

## Lokaal starten

Gebruik Node.js >=22.13.0 en de bestaande lockfile:

```sh
cd apps/web
npm ci
npm run dev
```

Controles:

```sh
npm run lint
npm run build
```

De build gebruikt standaard Vinext op Node voor Ubuntu. De oorspronkelijke Cloudflare/Sites-preview is opt-in met `LEON_CLOUDFLARE_PREVIEW=1`; die is niet de geteste lokale backendmodus. `project_id` in `.openai/hosting.json` is geen geldige live deployment. Voor de echte modus zijn server-side `LEON_BACKEND_URL`, `LEON_DASHBOARD_TOKEN`, `LEON_WEB_AUTH_FILE`, `LEON_WEB_SESSION_SECRET`, `LEON_WEB_SETUP_CODE` en `LEON_WEB_PUBLIC_ORIGIN` vereist. Geen secret als `NEXT_PUBLIC_` instellen.

Behoud het uiterlijk uit `DESIGN.md` bij backendintegratie. Vervang demo-state later door echte task-events, checkpoints, approvals en foutmeldingen, zonder de website opnieuw te ontwerpen.
