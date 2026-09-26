# Chat als bediening, Werk als overzicht

Stand: 26 september 2026. Vandaag, Chat, Werk en Memory zijn de echte
verbonden schermen; voorbeeld/verbonden schakelaars zijn verwijderd. `/shopper`
verwijst naar `/?space=flows`. Werk toont shopper-watches en overige echte
taken samen, met inklapbare kaarten, agent/statusfilters, compacte/ruime
weergave en voortgangsbolletjes. Leads, bronstoringen, geplande reacties en
gepauzeerde contacten komen uit de duurzame backend; geen verzonnen progressie.
De eigenaar stuurt shopper-opdrachten via de chat aan. Vandaag toont eerst de
agenda en een compact werkoverzicht; overige kaarten zitten onder een details-
sectie. De bestaande taakselectie-API blijft beperkt tot uitvoerbare taken;
`GET /api/work/status` toont afzonderlijk de echte status van max. 100 taken.

## Chatbediening

Een conservatieve trefwoordpoort leidt mogelijke opdrachten naar een begrensde
lokale M40-router. Alleen de laatste eigenaarsopdracht geeft bevoegdheid;
maximaal twee eerdere eigenaarberichten helpen verwijzingen begrijpen. De
router kiest uit vaste tools voor shopper create/update/pause/resume/search/
hold/status, Agenda/Gmail lezen, geheugen bewaren/zoeken, taak opslaan/status
of verduidelijking. Budgetten moeten letterlijk uit de actuele opdracht komen;
het model mag ze niet verzinnen. Bekende watch-IDs, veldlimieten en directe
werkwoorden worden gecontroleerd. Geen shell, vrije bestemmingen, aankoop of
betaling. Niet-ondersteunde opdrachten krijgen verduidelijking. Algemene taken
worden momenteel opgeslagen, niet stilzwijgend uitgevoerd.

Een duurzaam chat_actions-register claimt de uitvoering vóór de async thread.
Een tweede POST met dezelfde aanvraag-id en GET/herladen herhalen de tool niet.
Na een onderbreking langer dan vijf minuten tijdens routing/uitvoering wordt
de status onbekend: er is geen automatische herhaling van mogelijke effecten.
De gespreksgeschiedenis bevat alleen het bevestigde toolresultaat. Lokale tools
vereisen geen extra UI-approval. Betaalde normale modelchat behoudt zijn eerdere
kostencontract; de nieuwe opdrachten gebruiken uitsluitend de M40.

Shopper zoekt standaard Marktplaats en Vinted in één watch. Resultaten bevatten
bronmetadata; een ontoegankelijke bron verhindert de andere bron niet. Alleen
Marktplaats-contacten zijn aangesloten voor automatisch berichten sturen.
Vinted-berichten, TicketSwap-monitor en algemene agentuitvoering zijn nog open.

## Google OAuth en thuisnetwerk

De server heeft een PKCE/S256 OAuth-flow met tien minuten geldige, ondertekende
HttpOnly/Secure/SameSite-cookie, gebonden aan de Leon-sessie én de HTTPS-origin.
Alleen Agenda events readonly en Gmail metadata worden gevraagd. De vaste
Google-tokenhost wisselt de eenmalige code in. Alleen de refresh credentials en
werkelijk verleende scopes worden atomisch buiten de repository geschreven,
met mode 0600; codes/tokens verschijnen niet in redirects of errorantwoorden.
Een bestaande Leon-login is vereist vóór Google-autorisatie. Geen Google-
wachtwoorden worden ingevoerd of geïmporteerd.

De OAuth-client moet beide callbacks toestaan: de vaste DuckDNS HTTPS-origin en
de actuele server-owned HTTPS Quick Tunnel-origin uit LEON_WEB_TEMP_ORIGIN_FILE.
Vanaf een LAN-IP gaat Google verbinden eerst naar die werkende HTTPS-site; daar
logt de eigenaar met hetzelfde Leon-wachtwoord in. Daarna blijven login,
OAuth-state en callback op dezelfde origin. Voor de vaste publieke host blijft
de DuckDNS-callback gelden. Arbitrary Host-headers kunnen geen eigen callback
instellen. De tunnel-URL verandert bij een tunnelherstart; dan moet de nieuwe
callback opnieuw worden toegevoegd aan Google Cloud. Een permanente oplossing
voor het thuisnetwerk vereist lokale DNS/NAT-loopback-configuratie.

Op 26 september: lokaal web en Caddy HTTP 200; twee externe HTTP-meetpunten
bevestigen DuckDNS HTTP 200. Vanuit het eigen LAN loopt de publieke route vast.
De Quick Tunnel heeft HTTP 200. Een tussentijdse DuckDNS-update-timeout is bij
een tweede refresh hersteld; routermapping/timer blijven actief.

## Bewijs en grenzen

- 501 backendtests, 55 webtests, TypeScript en productiebuild geslaagd.
- Lint: nul errors, zeven warnings in de bestaande prototype-rootcomponent.
- Browser: compacte Vandaag, Google verbinden, één Werk-navigatie, filters,
  geopende shopperkaart met echte dots/leads/held-contact/deadline; geen
  voorbeeldschakelaars. Tweede chatbericht via de echte UI bevestigd.
- Live M40-toolrouter antwoordde met werkelijk actieve watch, nul leads en
  één held-contact, zonder model-only antwoord of dubbele uitvoering.
- Gezamenlijke echte zoekronde: 28 Marktplaats-advertenties + 1 Vinted-resultaat,
  nul passende 128GB-kandidaten, held-contact onaangeroerd.
- OAuth-codewissel en credentialfile zijn met neptransport getest; callback-
  selectie voor LAN/tunnel/publieke host op de productie-webserver gecontroleerd.
  Echte Google-consent/Agenda-API is pas bewezen na eigenaarconsent. Zolang
  configured=false staat, toont de UI de verbindknop en geen nepafspraken.

Inlogherstel: het wachtwoordformulier staat direct in de server-rendered HTML;
geen verborgen formulier achter een hydration-laadscherm. Native POST-formulieren
hebben dezelfde origincontrole, poginglimiet, scrypt en private cookie als JSON.
Een loginfout blijft een generieke redirect zonder wachtwoord in de URL. De app
zelf vereist JavaScript; een noscript-melding maakt dat expliciet. Geïsoleerde
native registratie/login, verkeerd wachtwoord en vreemde origin zijn getest.
