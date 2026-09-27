# M40 code bouwen vanuit Leon

Expliciet “Maak/bouw/schrijf een Python-tool/functie/script …” in chat zet de
letterlijke opdracht bij Leon Code in verenigd Werk. Geen extra modelroutercall.
Een afzonderlijke systemd-bouwwerker verwerkt één opdracht per keer; de normale
chatworker blijft vrij. De bestaande GPU-lease bepaalt wanneer inference mag.
OpenCode/GPT-OSS20B gebruikt de compacte read/edit/write-agent, vaste deadline
600s en de bestaande verse89C-guard. Geen betaalde model/providerfallback.

Korte private werkpaden en expliciete bestandslocaties voorkomen bewezen
padvergissingen door het lokale model. Alleen tool.py en test_tool.py worden
teruggelezen: reguliere bestanden, geen symlinks/extra bestanden, maximaal32KiB
per bestand, secretcheck, syntax en ten minste implementatie/testasserties.
Bronnen en hashes blijven in de private database; geen automatische hostimports.

Docker test uitsluitend een kopie van deze twee bestanden. De lokale testimage
is vooraf gebouwd uit een gepinde officiële Python-image en pytest8.4.2; bij
uitvoering wordt een werkelijk geïnspecteerde immutable image-ID gebruikt.
Geen netwerk, read-only root/source, niet-rootuid, geen capabilities,
no-new-privileges,64processen/256MiB/1CPU, kleine tmpfs en35s deadline.
Geen Docker-socket, env-bestand, host-home of GPU in de container. Cleanup
verwijdert uitsluitend de eigen willekeurig benoemde testcontainer; geen raw
containeroutput in chat. Code kan nog slechte tests schrijven: geslaagde tests
zijn bewijs van deze tests, geen bewijs van volledige opdrachtcorrectheid.

Deduplicatie bindt request-ID aan de volledige eigenaaropdracht. Gecontroleerde
GPU-yield/cooling wacht minimaal60s en herbouwt alleen ongebruikte private
bestanden. Onzekere afgebroken generatie blijft geblokkeerd zonder stille
herhaling. Verkregen workerlock bewijst dat een achtergelaten building-state
geen actieve worker meer heeft. Opgeslagen ready-artifact hervat de melding
zonder opnieuw model of tests te starten. Resultaat komt één keer in het
originele gesprek. De codegeneratiesubtaak kan klaar zijn, maar de hoofdtool
blijft open zolang registratie/aansluiting ontbreekt. Geen eigenaarreview
vereist voor deze geautoriseerde bouw- en teststappen.

## Doelserverbewijs, 27 september

Eerste proef faalde: M40 vergiste zich in een lange padnaam; geen geldige code
of installatie geclaimd. Met korte expliciete paden: echte M40-filebouw81.7s,
broncode en vier pytestcases opgeslagen; echte Docker-tests exit0, bewuste
foutcase exit1. Niet-root/readonly/no-host-file/no-host-backend/capdrop-probes
ook werkelijk geslaagd. Docker29.1.3, eigenaar heeft docker-groep toegekend;
sg activeert die toegang ook vanuit bestaande gebruikerssessies.

Volledige geïsoleerde chatserviceproef: opdracht GB→MB, action-ack, echte M40
bouw68.7s, Docker-tests geslaagd, drie chatberichten inclusief terugbezorging,
cost0. Hoofdtaakblocked: aansluiting nog niet uitgevoerd. Geen productie-
conversationtest of reeds beschikbare algemene chat-tool claimen. Production
bouwwerker/timer gedeployd; geen dummy opdrachten in eigenaar-database.

Volgende: geteste functies registreren en vanuit chat uitvoeren in dezelfde
containergrenzen; daarna bestaande MCP-tools onderzoeken/installeren en
nachtelijke vaardigheidstaken verbinden. Volledige repo-patchtests/deployment
blijven een afzonderlijke keten, niet bewezen door deze standalone-tooltests.

Verificatie:631 volledige backendtests,11 gerichte bouw-/containertests,
57 webtests, TypeScript/build geslaagd; lint0 errors/7 bestaande warnings.
Echte Docker-test via systemd-gebruikersservice exit0; geen eigen testcontainers
achtergebleven. Backend/web/worker/guard en bouwwerktimer active/enabled.
Containeropties: https://docs.docker.com/reference/cli/docker/container/run/ .

## Geteste functies gebruiken, 27 september

Na succesvolle Docker-tests registreert Leon automatisch geschikte sync
Python-functies met JSON-invoer, type-/parametercontrole en de geteste bronhash
plus image-ID. Functies worden uitsluitend in Docker geladen; op de host leest
AST alleen de handtekening. De eerste ondersteunde functie is de werkelijk door
de M40 gebouwde gb_to_mb. Die staat nu in de productiecatalogus en Werk; echte
productie-aanroep64GB gaf65536MB. Bron is het eerder bewezen M40-artifact; niet
opnieuw gegenereerd. Dit is een lokale rekenfunctie, geen live MCP-integratie.

Vraag in chat welke tools beschikbaar zijn, of bijvoorbeeld: “Gebruik mijn
nieuwe tool en reken64GB om naarMB.” De M40-router krijgt alleen geregistreerde
metadata en kiest een exact ID en gevalideerde argumenten. Een afzonderlijke
achtergrondservice voert de functie uit en bezorgt het resultaat in dezelfde
chat/Werk. Geen extra goedkeuring voor deze geautoriseerde lokale uitvoering.
De gewone web/backendservice krijgt geen containercode in zijn proces.

PrivateTmp in de systemd-gebruikersmanager bleek groeps-ID's te remappen naar
65534; sg kon de nieuwe Docker-groep daar niet verkrijgen. Beide Docker-workers
gebruiken daarom de echte host-groeps-ID's. Docker zelf houdt code offline,
nonroot, read-only en begrensd. Tijdelijke bronkopieën staan op een vaste
host-zichtbare private plek zodat ook de Docker-daemon ze kan lezen; na afloop
opgeruimd. De backend blijft ongewijzigd afgeschermd en wekt alleen de vaste
functiewerker. Een timer herstelt gemiste wakeups.

Aanroep maximaal15s/8KiB uitvoer; stdin is begrensde JSON en stdout wordt tijdens
het lezen begrensd, niet achteraf met een onbeperkte communicate(). Geen raw
fout/logoutput in chat. Request-ID bindt functie en argumenten; opgeslagen
resultaat/melding herstelt zonder nieuwe uitvoering. Onzekere uitvoering wordt
geblokkeerd zonder automatische replay. Gewijzigde bron verdwijnt uit catalogus
en wordt vóór uitvoering afgewezen. Onbewezen externe integraties worden niet
als afgeronde tool geregistreerd omdat lokale tests geen echte accountacties
bewijzen. Complexe signatures/async functies en netwerk-/accounttools zijn
vervolgwerk, naast de bestaande echte Google/shopperconnectors.

Bewijs: geteste M40-functie geregistreerd en parent done. Geïsoleerde echte
chatservice + M40-router41.3s + systemd/Docker41.9s totaal leverde65536 in hetzelfde
gesprek; echte achtergrondservice-aanroep128GB gaf131072. Overmatige uitvoer
werd na0.4s afgewezen; oneindige lus na15.1s gestopt; eigen containers opgeruimd.
Dit bewijst deze berekeningen en keten, niet alle toekomstige tools.

Laatste productieacceptatie: geauthenticeerde webbridge→backend→echte M40-router
→vaste achtergrondservice→Docker→oorspronkelijke chat,10s, bevestigd65536.
Gesprek heet Controle lokale functies, geen credentials gelogd. Dit is een
werkelijke HTTP-webflow, geen nieuwe native-browser-klikproef. Backend640tests
plus36 gerichte registry/bouw/container/routerchecks geslaagd; webbron ongewijzigd.
Geteste bron/installatie en functie-uitvoering staan ook in productie-Werk.

## Nachtelijke vaardigheidsontwikkeling

De22:00-service voert na conversation_learning en skill_discovery ook
skill_development uit. Concrete offline-functies worden automatisch gekoppeld
aan bestaande bronopdrachten of als nieuwe bouwsubtaak gequeued. De originele
vraag blijft in de brief. UUID/journalbind voorkomt dubbele builds. Maximaal
twee nieuwe beslissingen per run; wachtende vragen/fouten krijgen24h cooldown.
Nieuwe bouw hangt onder de oorspronkelijke vaardigheid in Werk. Code Worker
reconcile sluit die taak alleen bij geteste bron+werkelijke catalogusregistratie
+afgeronde codehoofdtaak. Gewijzigde doelen krijgen geen oude voltooiing.
Meldingen gaan waar mogelijk terug naar het oorspronkelijke gesprek.

Extern-account/MCP/software-installatie is geen lokale functie. Die vaardigheid
blijft open tot aansluiting bewezen is; Magister verwijst naar de bestaande
schoolaanmelding/2FA. Catalogusmetadata bewijst geen gratis/licentie/werking.
Noch deze stap noch de standalone-container bewijst volledige repo-patchtests
of automatische deployment van gegenereerde wijzigingen.

Nachtketen-doelserverproef27september: echte reflectie+catalogus+besluit;
herproef149.1s leverde M40-functie zonder echte tests, correct failed/blocked,
geen tool geïnstalleerd. Prompt daarna aangescherpt naar tests-eerst/korte
bestanden; die gewijzigde prompt nog niet als nieuwe succesvolle bouw claimen.
Eerder werkelijk geteste M40 GB→MB-bron automatisch hergebruikt door
skill_development: oorspronkelijke vaardigheiddone, geen extra model/search.
651full backend/35target na promptwijziging/57webtests, tsc/build, lint0errors.
