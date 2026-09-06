# Bestaande Gaia-frontend

Bron: Codex-taak **Maak AI-assistantwebsite prachtig**, broncommit `f5e8426` van 28 augustus 2026. De eigenaar heeft deze website op 6 september 2026 aangewezen als frontend van Leon.

Deze kopie bevat 15 bestaande bron-, configuratie-, lock- en assetbestanden. Ze zijn bij het kopiëren byte-voor-byte met SHA-256 gecontroleerd. De oorspronkelijke werkmap en publicatie zijn niet gewijzigd. De hostingconfig bevat hier een lokale placeholder in plaats van de bestaande deploymentidentiteit.

## Wat bestaat

React 19, TypeScript, Next/Vinext, Vite, Motion en Lucide. Er zijn aparte Vandaag-, Chat-, Werk- en Memory-ruimtes, een frosted navigatie, de Gaia-entiteit, agentselectie, missiestatus, checkpoints, pauzeren/hervatten, approval-previews en een self-learning-preview.

`PRODUCT.md` beschrijft de data expliciet als synthetisch. `app/page.tsx` gebruikt lokale React-state en timers voor de voorbeelden. Er zijn in deze bronkopie geen API-routes, echte modelcalls of duurzame taakopslag. De getoonde ETA en voortgang zijn voorbeelden.

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

De huidige build gebruikt de oorspronkelijke Vinext/Cloudflare/Sites-scaffold. Een werkende frontendbuild betekent nog niet dat deployment op de Linux-server is ingericht. `project_id` in `.openai/hosting.json` is geen geldige live deployment; configureer hosting pas bij een expliciete deploymenttaak. Zie de actuele controle-uitkomsten in `../../docs/handoff.md`.

Behoud het uiterlijk uit `DESIGN.md` bij backendintegratie. Vervang demo-state later door echte task-events, checkpoints, approvals en foutmeldingen, zonder de website opnieuw te ontwerpen.
