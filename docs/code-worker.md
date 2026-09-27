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
