# Leon / Gaia — uitvoeringsbacklog

**27 september, schoolaanmelding en begrensde M40-coder gedeployd:**
Magister heeft nu in Vandaag → Je agenda → Magister koppelen een eigen
serverformulier voor Microsoft-wachtwoord en 2FA-code/Authenticator-bevestiging.
School/account blijven alleen in private configuratie. Magister accepteerde het
leerlingnummer en redirectte werkelijk naar Microsoft; live status password_needed,
HTTP200 via de webbridge. Een opgeslagen login-HTML is geen ingelogde sessie.
Geen schoolwachtwoord/2FA ontvangen of geprobeerd; agenda-toegang nog onbewezen.
Laatste browserproef vond CDP-tabselectie gedeeld tussen sessiealiases; school
wordt nu direct via vaste loopback-CDP-pagetarget aangesproken, zonder focus
te wijzigen. Regressie en echte HTTP200/password_needed na wisselen bewezen.
Wachtwoord/code alleen via lokale browser-CDP-verbinding, geen chat/geheugen/DB; DB bewaart alleen
verzoeknonce/tijd. Exacte host/accountcontrole, deduplicatie en geen automatische
retry bij onbekende uitkomst. Statuscontrole door eigenaar; geen MFA-bypass.

Coding-wrapper gebruikt nu bestaande verse thermische guard i.p.v. steeds
nvidia-smi te starten, met begrensde runtime en cleanup van de eigen procesgroep.
Compacte OpenCode-config met korte prompt/read/edit/write verlaagt prefill.
Echte GPT-OSS20B/M40-proef: read/edit/readback in tijdelijk bestand, exit0,
charged0, piek59C. De twee regels voor leerlingnummerextractie zijn na bronreview
in de schoolconnector overgenomen en getest. Dit bewijst nog geen algemene
Code Worker vanuit Leon of uitvoering van willekeurige gegenereerde code.
Docker is geïnstalleerd maar gebruiker heeft geen sockettoegang; OS-sandbox en
nachtelijke autonome codebouw/deployment blijven open.

Verificatie: 620 volledige backendtests en16 gerichte checks incl. helper/CDP-tabselectie;
57 webtests, TypeScript/build geslaagd, lint0 errors/7 bestaande
warnings. Backend/web/worker/guard active. React-review: eventgestuurde lazy
status, gelabelde invoer, busy-guard en geen browseropslag. Browserformulier
Schoolwachtwoord/School aanmelden/Status controleren werkelijk zichtbaar.
Volgende: eigenaar meldt zich in Leon aan en bevestigt2FA; daarna echte
Magister-agenda lezen en aansluiten op planner/chat. M40-codeworker verder
verbinden zodra gecontroleerde doelhostchecks mogelijk zijn.


**27 september, automatische MCP-zoekstap aangesloten:** skill_discovery draait
als ExecStartPost na de22:00-gesprekreflectie. Per run maximaal2 nieuwe
vaardigheidstaken; herkenbare productnamen direct, onbekende via bestaande M40
achtergrondprioriteit. Geen Firecrawl/OpenAI/abonnement. Vaste officiële HTTPS-
catalogus, version=latest, hoogstens2 zoeknamen en5 kandidaten; metadata begrensd,
geen redirects, geen pakketargumenten/code uit het antwoord uitvoeren. Op deze VM
time-out bij directe registry-TLS; bestaande serverproxy via urllib levertHTTP200.
Catalogusbeschrijvingen zijn brondata; prijs/licentie/werking blijven onbekend.

Echte zoeksubtaak onder de oorspronkelijke vaardigheid in verenigd Werk; alleen
zoeksubtaak gaat done na opgeslagen providerresultaat. Hoofdvaardigheid blijft
open tot installatie/configuratie/werkelijke tools bewezen zijn. Journal hervat
meldingen zonder model/netwerkreplay; fouten blokkeren zoeksubtaak en wachten24h,
expliciete onderhoudsretry alleen voor terminal retry-status. Nieuwe taakbrief
krijgt eigen zoekresultaat; oude zoekresultaten verdringen geen nieuwe opdrachten.

Doelserver: eigenaarwens Magister-agenda als taak geregistreerd. Eerste M40-query
ongeldig (te algemene naam), daarna vaste productnaam; tweede proef directe TLS
time-out. Na proxycorrectie werkelijk afgerond: magister-query,0 kandidaten,
zoeksubtaakdone/hoofdtaaknew en één melding.0 resultaten zijn geen bewijs dat er
elders geen connector bestaat. Extra catalogusprobe calendar:5 kandidaten,
3 bronrepositories, geen bewezen installatie of prijs. Bestaande Google-
koppeling blijft de werkelijke plannerconnector. Bron:
https://registry.modelcontextprotocol.io/docs .

Volgende: voor relevante kandidaten GitHub/licentie/vereiste accounts onderzoeken
en echte installatie/verbinding/test uitvoeren; anders eigen connector bouwen.
Magister-school/auth nog onbekend. GLM5.2/Colibri wacht extra schijf/RAM.
604 volledige backendtests, systemd/diffcheck geslaagd. Geïntegreerde productie-
oneshot reflectie+ExecStartPost eindigde success/exit0; eerder afgehandelde
zoekstap niet herhaald, geen dubbele melding. School/portal-URL aan eigenaar gevraagd.

**27 september, eerste echte zelfleerketen gedeployd:** nieuwe module
conversation_learning gebruikt bestaande Leon-chat, Memory, taken en owner_updates.
Dagelijks22:00 Europe/Amsterdam via enabled/active timer; maximaal12 nieuwe
gebruikersberichten uit afgelopen7dagen, batches3 en achtergrondprioriteit op
bestaande M40. Geen Firecrawl/OpenAI of betaalde providerfallback. Geheimhoudende
berichten worden vóór inference uitgesloten en als afgehandeld gemarkeerd.
Uitsluitend letterlijke broncitaten; een expliciete eigenaaruitspraak is nodig
voor voorkeuren/tools. Modelinterpretaties worden niet als geheugen opgeslagen.
Nieuwe voorkeuren komen actief als preference in bestaande chatcontext; mogelijke
conflicten via conservatieve woordoverlap blijven candidate/conflicted zonder
oude entries te wijzigen. Dit is nog geen volwaardige semantische conflictoplosser.

Tool/skillwensen worden concrete taken met bouwprompt en bronverwijzing in
verenigd Werk, owner Leon Zelfleren. Vragen staan daar en in de gededupliceerde
chatmelding. Taken zijn geen bewijs van installatie/uitvoering. Journal vóór
mutaties, exclusieve proceslock, stabiele source-deduplicatie en hervatten van
pending resultaat voorkomen herhaalde inference na een meldingstoring. Geen
nieuwe melding als niets geleerd is. Een crash precies tussen effect en journal-
update kan nog een telling/melding missen, maar veroorzaakt geen dubbele bron.

Productieservice doorliep12 echte Leon-gebruikersberichten in4 lokale batches;
geen duurzame nieuwe leerpunten, dus terecht geen meldingen. Kleine geïsoleerde
M40-proef met een bestaande echte eigenaaruitspraak:2 nieuwe voorkeuren en
memory_used_in_chat=true, charged0. Eerste strikte validatorproef wees een
letterlijk vervolgzin-citaat af; explicietheid wordt nu in het hele bronbericht
gecontroleerd. 588 volledige backendtests +10 gerichte tests na deze correctie;
systemd/diffcheck geslaagd. UI ongewijzigd. Geen trainingsgewichten aangepast.

GLM5.2/Colibri nog niet aangesloten: projectdocumentatie noemt circa372GB disk en
minimaal16GB RAM; deze VM heeft129GB vrij/9.3GB RAM. Eigenaar gevraagd om grotere
schijf/RAM of voorlopig bestaande M40. Bron: https://github.com/JustVugg/colibri .
Niet stilzwijgend een betaald API-abonnement openen. Volgende: nuttige skilltaken
met bestaande gratis MCPs verbinden en daadwerkelijke code/test/rollback-worker.

**27 september, Google Calendar-write live bewezen:** writegrant nu true.
Eigen primaire tijdelijke afspraak zonder gasten/herhaling daadwerkelijk gemaakt,
gewijzigd en verwijderd; elke toestand teruggelezen. Google retourneert na
DELETE soms HTTP200/status=cancelled als tombstone. Eerste extra smoke-assertion
verwachtte alleen404/410 en was fout; tweede correcte proef bevestigde volledige
create/update/delete-keten en cancelled. Geen testafspraak achtergelaten. Nog
open: multi-tool-planning, andere agenda's en Gmail meer dan metadata.

**27 september, gezamenlijke GPU-prioriteiten gedeployd:** chat en inkomende
shopperreacties vóór zoeken, achtergrondwerk en coding. Wachttijd verhoogt de
prioriteit zodat oude taken ook starten; lopende generaties worden niet afgebroken.
SQLite bevat uitsluitend tijdelijke procesmetadata; dode/reboot-PID tickets worden
opgeruimd. Echte subprocessproef bevestigt chat vóór achtergrondwerk; echte
coding-wrapper stelt uit met exit75 voor wachtende chat. Generatievrijgave hangt
niet af van een nieuwe databaseverbinding. Workerlease omvat wachten én generatie.
Live chat gaf “Leon is bereikbaar.” via Ollama met charged0. 579 backendtests.
Nog open: adaptieve modelkeuze/batching en Code Worker vanuit chat. Volgende
onderdeel op eigenaarverzoek: echte gesprekreflectie en vaardigheden-todo om22:00.
Google writegrant is op27september inmiddels true; echte writeproef nog nodig.

**26 september, globale M40-temperatuurbewaking gedeployd:**
leon-m40-guard.service is enabled/active met een doorlopend nvidia-smi/NVML-
meetproces voor GPU0 (op deze VM geverifieerd Tesla M40 24GB). Losse NVML-
initialisatieprobes konden hier langer dan acht seconden vastlopen; het vaste
meetproces levert nu iedere seconde een verse meting. Bij >=89C of ontbrekende
metingen stopt alleen Leons eigen Ollama-service; bij <=80C gedurende 30 seconden
kan de bewaker uitsluitend zijn eigen stop hervatten. Monotone tijd voorkomt
verkorten van de afkoelperiode door een klokcorrectie. Een handmatige service-
stop wordt niet automatisch ongedaan gemaakt. Proxmox houdt de fysieke fan.

Backend/worker starten na de bewaker via M40-specifieke systemd-drop-ins. Alle
lokale generatiepaden en de coding-wrapper vereisen een verse passende status.
Bij afkoeling blijft lokaal wachtrijwerk staan zonder retries te verbruiken;
andere lokale checks kunnen door. Queuebereiding gebruikt nu werkelijk zijn
meegegeven LocalModelConfig. Incidenten/resultaat in verenigd Werk (Leon Server)
en gededupliceerde chatmeldingen; onveranderde gezonde metingen blijven stil.
Meldingspoging wordt bewaard en na daemonherstart opnieuw bezorgd.

Echte gecontroleerde foutproef: een onleesbare meting werd gesimuleerd bij een
koele idle GPU; eigen Ollama-stop bevestigd. Eerste herstelproef faalde door
NVML-initialisatiehangs; na wijziging naar continu meten bevestigde de productie-
bewaker de afkoelperiode en eigen serviceherstart. Geen fysieke 89C-stressproef.
Daarna echte chatpreview provider=ollama/reservering0, chatantwoord “Leon werkt
lokaal”, job succeeded/charged0. Guard/Ollama/backend/worker active; verse
metingen onder de grens. 573 backendtests en bash/systemd-controles geslaagd.
Fake-modeltests gebruiken een eigen GPU-lock zodat productie-coding ze niet
blokkeert. Frontend ongewijzigd; eerdere 56 webtests/typecheck/build blijven geldig.

OpenCode/Qwen op de M40 kreeg één kleine read-only review van thermal_guard.py,
met maximaal 120 seconden. De procesgrens werd bereikt na step_start, zonder
verdict of wijziging; dit is geen geslaagde codereview. Lease vrij en GPU idle
na afloop. Niet herhalen zonder de OpenCode-context-/prefillkosten te verbeteren.
Code Worker vanuit chat, schedulerprioriteiten en gezamenlijke nachtverbetering
blijven open. Google write-consent en Docker-groepstoegang blijven eigenaarstappen.

**26 september, echte vrije-momentenplanner:** calendar.find_slots is vanuit
chat aangesloten op volledige Google-events van de primaire agenda. Bestaande
planner-gapberekening wordt hergebruikt zonder sampledata. Overlap, all-day,
nonblocking/cancelled events, grenzen, verleden en Amsterdam-DST zijn afgedekt.
Afgekapt of onbekend resultaat levert geen vrijverklaring. Defaults 09:00–17:00
staan expliciet in het antwoord; overige agenda's zijn niet meegenomen.

Eerste echte chatproef ontdekte een M40-schemafout (datums bij kloktijdvelden).
Het schema is verduidelijkt en de adapter accepteert ook datumkloktijden met
geverifieerde dag/Amsterdam-offset; ontbrekende/onjuiste gegevens geven een
vriendelijke verduidelijking. Vervolgbericht in hetzelfde echte gesprek ging
chat → M40-router → Google → complete met één bevestigd morgenvenster. Geen
agenda-mutatie/Firecrawl/OpenAI-call; direct providerpad ook live bevestigd.
Schrijfrecht blijft ontbreken; de eerder gevraagde extra toestemming staat open.
Samengestelde planning en rekening houden met andere agenda's blijven open.
561 backendtests geslaagd; services active en de feature op de doelserver.
Frontend is ongewijzigd; de vorige 56 webtests/typecheck/build blijven geldig.

**26 september, Calendar-writer gedeployd:** chat ondersteunt eigen afspraken
maken, wijzigen en verwijderen; wijzigingsopdrachten halen actuele Google-events
op zodat echte event-IDs beschikbaar zijn. Amsterdam-tijden inclusief DST worden
gevalideerd. Iedere opdracht krijgt een duurzame identiteit en Planner-taak in
Werk. Ontbrekend consent blokkeert zichtbaar; de worker hervat automatisch na
werkelijke scopegrant en meldt één keer terug in het oorspronkelijke gesprek.
Onzekere uitvoering wordt nooit opnieuw verstuurd; maximaal vijf begrensde
readbacks kunnen de daadwerkelijke Google-toestand alsnog bevestigen.

Persoonlijke primaire-agenda-items zonder gasten of herhaling worden ondersteund;
geen uitnodigingen, gedeelde/terugkerende afspraken of multi-tool-autoplanning.
Wijzigingen gebruiken versiecontrole en worden pas done na providerreadback.
Schrijfrecht is enabled=true maar werkelijk granted=false: actuele accounttoegang
blijft alleen lezen. Vandaag toont de browser-bewezen knop “Afspraken beheren
inschakelen”; aanvullend Google-consent is bij de eigenaar gevraagd. Echte writes
zijn dus nog niet live bewezen. Agenda/Gmail-readprobes na deployment: HTTP200,
0 events en 5 metadata-items (geen persoonlijke inhoud opgeslagen in docs/logs).
547 backendtests, 56 webtests, typecheck/build geslaagd; lint nul errors/zeven
bestaande warnings. Backend/web/worker herstartten idle en staan active.

**26 september, Werk en klikbare researchbronnen:** agentfilter bevat de
werkelijke Leon-rollen (Research/Server/Writer enz.). Een voltooide taak toont het
bevestigde opgeslagen resultaat, inclusief de echte bronlinks, in plaats van
alleen de ruwe modelcheckpointtekst. HTTPS-links zijn klikbaar in chat én Werk;
geen HTML-rendering van modeltekst. Browserproef Research + Afgerond: precies één
researchkaart, bronnenlabel en drie HTTPS-anchors. Companion naar vrije
headerruimte verplaatst; browserbounding-boxes bewijzen geen overlap met de
opdrachtknop. Typecheck/build en 55 webtests geslaagd; lint nul errors/zeven
bestaande warnings. Tijdelijke browserauthfile is na controle verwijderd.

**Google is nu werkelijk verbonden:** actuele serverstatus configured=true.
Echte geauthenticeerde Calendar-preview voor de komende week slaagt (nul
gebeurtenissen); Gmail-metadata-preview levert vijf echte items. Geen persoonlijke
inhoud in logs of repository. De planner kan nu lezen; afspraken toevoegen,
wijzigen en verwijderen vereist nog de writerintegratie en aanvullend consent.
Docker-groep is nog leeg, dus coding-testsandbox blijft zonder hosttoegang.


**26 september, gedeelde GPU-beurt en zuinigere routing:** gewone chat telt
een gecachet eigen Qwen-model niet langer als bezet. /api/ps toont residentie,
geen generatie; daadwerkelijk gebruik wordt door een gedeelde flock bewaakt.
Alle lokale transportcalls (chat/router/shopper/tasks) delen één lease; de M40-
coding-wrapper gebruikt dezelfde inode en weigert starten bij bezetting. Een
bezet slot wordt begrensd afgewacht; fouten geven de lease altijd vrij. Een
ander resident model of onleesbare status blijft conservatief bezet. Bestaande
Ollama heeft al NUM_PARALLEL=1 en MAX_LOADED_MODELS=1.

Echte warme chatpreview: local_busy=false, provider=ollama, reservering=0.
Echte wrapperproef met gehouden Python-lease: exit75, coding niet gestart;
lease na afloop vrij. 529 backendchecks; bash-syntaxcontrole geslaagd. De
89C-codingguard blijft behouden. Gezamenlijke prioritering en een globale
thermische watchdog voor alle lokale calls blijven nog open.


**26 september, echte serveragent:** wekelijkse zondagcontrole om 10:00
Europe/Amsterdam actief via leon-server-watch.timer. Vaste OS-probes controleren
Leon backend/web/worker/Ollama, vrije schijf en M40-temperatuur. Alleen eigen
backend/web/worker kunnen gericht herstarten, maximaal één poging per service
per zes uur; herprobe bewijst de eindstatus. Ollama wordt niet automatisch
herstart, en een hete/onleesbare GPU verhindert automatische workerherstart.
Geen algemene shelltool vanuit chat. server.status/check zijn aangesloten op
het vaste lokale toolpad.

Routine-uitvoering verschijnt met eigenaar/resultaat in verenigd Werk. Alleen
nieuwe problemen, herstel of een herstelpoging maken een duurzaam gededupliceerd
bericht in Leon updates; stabiele checks sturen geen chatmelding. De echte
herstelproef stopte de idle worker, waarna de serveragent hem aantoonbaar
herstartte: alle vier services active, M40 36C, taak done. Proefmeldingen waren
uitgeschakeld. Eerste gezonde wekelijkse run uitgevoerd, volgende zondag
27 september 10:00 Amsterdam. Browser bevestigde twee afgeronde serverkaarten
met Leon Server, werkelijk resultaat en temperatuur. 521 backendtests,
typecheck/build geslaagd; lint nul errors/zeven bestaande warnings.
De chatstatus-proef vond ontbrekende recovery-metadata bij read-only status;
describe accepteert nu beide vormen en heeft een extra regressietest.


**26 september, geïntegreerde webresearch:** expliciet onderzoek vanuit chat
roept de bestaande Firecrawl search-only connector aan en zet de brongegevens
op de lokale M40-wachtrij. Geen OpenAI-synthese. Resultaat krijgt de daadwerkelijk
gevonden bronlinks in chat en Werk. Zoeksnippets worden als onbetrouwbare data
behandeld; geen claim dat volledige paginas zijn gelezen. Sensuele research
wordt niet naar Firecrawl verstuurd. Dagbudget blijft gedeeld met de bestaande
research-API; budget op/fout geeft een concrete melding zonder automatische retry.

Echte chat → router → Firecrawl → M40 → done-task → terugbezorging bewezen:
1015 tekens en drie echte bronlinks. Twee live searchproeven samen vier credits,
vandaag nog zes beschikbaar. Backend 515 tests, web 55 tests geslaagd;
productiebuild/typecheck eerder deze wijzigingsronde geslaagd. Extra GPT-OSS/M40 read-only codecontrole
stopte na 180 seconden zonder reviewresultaat (alleen glob); model daarna
ongeladen voor normale chat. Niet als geslaagde coding-review meetellen. Google-consent en Docker-toegang zijn
nog eigenaarstappen; daarop wachten houdt andere onderdelen niet tegen.


**26 september, automatisch geheugen in gewone chat:** relevante actieve
geheugenitems en maximaal drie voorkeuren gaan nu mee in de begrensde prompt.
Verwijderde, verlopen, kandidaat- en conflicterende items worden uitgesloten.
De selectie gebeurt in dezelfde SQLite-transactie, zonder tweede schrijf-lock.
Persoonlijke geheugencontext blijft verplicht op de lokale M40; veranderde
context maakt een oude preview ongeldig. Drie regressies + bestaande chat/task-
checks: 27 geslaagd. Geen automatische opslag van alle gesprekken toegevoegd.


**26 september, persoonlijke achtergrondtaken en researchbudget:** gewone
schrijf-, plan- en analysetaken vanuit chat draaien daadwerkelijk via de M40-
wachtrij. Resultaten worden eenmaal terugbezorgd in het oorspronkelijke gesprek
én getoond in verenigd Werk. Pauzeren/hervatten/annuleren via chat aangesloten;
expliciet “later” bewaart alleen, achtergrondopdrachten worden gestart. Echte
M40-checklistproef leverde drie chatberichten en een afgeronde taak. Geen externe
acties of feitenverificatie claimen bij zulke teksttaken. Volledige backend 508
checks geslaagd; web typecheck/build, lint nul errors/zeven bestaande warnings.

Eigenaar autoriseerde maximaal 10 bestaande Firecrawl-credits per Amsterdam-dag.
Duurzame atomische reservering rekent 2 credits per search-only poging; fouten
houden de reservering en dezelfde preview kan niet opnieuw betaald zoeken.
Bestaande providerbalans wordt vooraf gelezen; geen billing/recharge-endpoints.
Live call: drie docs.python.org-bronnen, creditsUsed=2, vandaag 8 over. Bron:
https://docs.firecrawl.dev/features/search#cost-implications. Chatresearch en
M40-synthese blijven de volgende integratiestap. Nieuwe HTTP-budgettest dekt
het doorgeven van de serverconfiguratie; nog apart draaien.


26 september, chat/werk/Google: alle echte opdrachten samen in inklapbaar Werk,
met filters en progressiebolletjes; aparte Shopper-tab en voorbeeldschakelaars
verwijderd, Vandaag compact. M40-chatrouter bedient bounded shopper-/Google-/
geheugentools met duurzaam geen-dubbele-uitvoering-register. Gezamenlijke echte
zoekronde MP+Vinted: 29 advertenties, geen passende 128GB-set, 64GB-contact blijft
op pauze. Google PKCE-callbacks voor vaste HTTPS-host én actuele Quick Tunnel;
LAN-start verhuist eerst naar HTTPS met eigen Leon-login. Eigenaar voegt tweede
callback toe; echte Google-consent/Agenda-call nog open. DuckDNS extern twee
HTTP 200-metingen, thuis NAT-loopbackprobleem: lokale IP of HTTPS-tunnel gebruiken.
501 backendtests, 55 webtests, typecheck/build geslaagd; lint nul errors/zeven
prototype-warnings. Zie `docs/chat-work-google.md`.


**26 september, owner-shoppercorrecties:** 64GB-contact op pauze zonder
antwoord/afwijzing; 128GB prioriteit voor 21 dagen, daarna 64GB reserve. Eerste
nieuwe zoekronde: 28 advertenties, geen passend 128GB-aanbod. Openingsbiedingen
volgen gewenste hoeveelheid + korting: EUR45 voor vijf → EUR30 voor vier;
volledige set van vier voor EUR45 → EUR35. Informele korte berichten.

**26 september, shopper:** eigen Leon-worker, M40-selectie, duurzame wekelijkse
watch en `/shopper`-bediening gedeployd. Eerste DDR3 ECC-watch live gezocht en
lokaal door Qwen beoordeeld. Contact via zichtbare Marktplaats-dialoog aangesloten;
geen aankoopflow. Serverbrowser en private Marktplaats-sessie live bevestigd; Mac niet meer nodig.
DOM-meldingstrigger + duurzame vertraagde replies aanwezig (15–45 minuten,
08:00–23:00 Amsterdam), lokale counteroffers/vragen/afwijzing en owner-ready
status. Eerste echte Leon-contactbezorging via de serverbrowser bevestigd door
teruglezen van het eigen bericht. Volgende: echte inkomende notificatie en
vertraagd antwoord end-to-end bewijzen; daarna Vinted-berichten en TicketSwap-eventmonitor. Zie `docs/shopper-worker.md`.

**25 september, chat en live weer:** Gaia's verbonden chat toont na verzenden
zichtbaar de reviewkaart en scrollt daar automatisch naartoe; de demo-toast wordt
alleen nog in het ontwerpvoorbeeld gebruikt. Leon blijft in chat compact naast
de kop staan. Daarnaast gebruikt Gaia Vandaag nu een echte alleen-lezen
Open-Meteo-call voor vast Amsterdam. Host, locatie, velden en drie dagen staan
server-side vast; antwoord is maximaal 64 KiB, wordt dubbel gevalideerd, tien
minuten gecachet en volledig via de connectoraudit gevolgd. Bron en CC BY 4.0
staan in de kaart. Echte call plus cache-hit en geldige auditketen zijn op de
doel-VM bewezen. Volledige stand: 448 backendtests, 51 webtests, TypeScript,
productiebuild en lint met nul errors/vijf bestaande warnings. Zie
[weerconnector](weather-readonly.md). Google/Firecrawl-credentials en de
self-improvement-doelcontainer blijven open.

**25 september, publieke website:** `https://leon-ai-assistant.duckdns.org`
heeft een geldig certificaat en extern HTTP 200. De webapp vraagt bij eerste
gebruik om een eenmalige instelcode en een zelfgekozen wachtwoord, daarna om
alleen het wachtwoord. Het productieaccount is geregistreerd. Routerlease,
DuckDNS en TLS worden door user-systemd onderhouden. Geïsoleerde registratie-
en loginflow, API-toegang en browserweergave zijn getest; zie
[publieke toegang](public-access.md). LAN NAT-loopback ontbreekt vermoedelijk;
de tijdelijke tunnel is beschikbaar als fallback. Google/Firecrawl-accounts en de
self-improvement-doelcontainer blijven de eerstvolgende productstappen.

Dezelfde dag rapporteerde de read-only doelserver-preflight een Tesla M40 24GB,
driver 580.178.04, 10 CPU-threads en 9.3 GB RAM. De geïsoleerde delivery-smoke
doorliep setup, auth, doctor, backup, stop en restore met geldige SQLite-
integriteit. Zie [doelserverbewijs](server-preflight-evidence-2026-09-25.md).

**21 september, doelserver:** de lokale user-systemd-units draaien. Chat via
Ollama/Qwen 14B op de Tesla M40 is end-to-end bewezen; OpenCode/GPT-OSS 20B
heeft echte file read/edit/readback uitgevoerd met 80C piek. M40-coding-agent
en pinned setup staan in `scripts/`. De 89C-afslag is gebruikerskeuze, geen
duurproef; Proxmox-fan-RPM is vanuit de VM onbekend. Zie
[M40-bewijs](m40-deployment-evidence.md). Echte geautoriseerde text-only
agent-runs gebruiken nu dezelfde duurzame Ollama-wachtrij; de echte M40-proef
bleef op 71C en eindigde reviewbaar. Volgende productstap: connectoracceptatie,
self-improvement-sandbox en volledige scenario's.

**14 september, OS-sandboxkern:** fail-closed rootless Podman-contract toegevoegd
en aan self-improvement API/Gaia gekoppeld. Immutable image en exact base commit,
root-owned executable/inode, lokale rootless cgroup-v2/seccomp-probe, vaste
network/proxy/image-volume/filesystem/process/resourcegrenzen en non-root smoke
zijn verplicht. Workspacepaden worden niet gemount: toegestane bytes gaan via
descriptor-veilige reads naar private read-only snapshots. Output is tijdens
uitvoering begrensd en geredigeerd; cleanup is verplicht voor succes. 15 gerichte
sandboxtests en volledige backend 368 tests + twee subtests, 46 webtests,
typecheck/build/lint geslaagd. Reviews zonder resterende P1/P2. API/approval en Gaia binden nu exact execution
mode, policyhash en imagecommit, met durable sanitized testbewijs; static blijft
default. Open: Podman ontbreekt op de doel-VM; doelimage bouwen/pinnen,
Ubuntu-hostacceptatie en browserbewijs
voor static/Podman-modi. Zie [OS-sandbox](os-sandbox.md).

**13 september, agenttaaklevenscyclus:** geaccepteerde lokale agentruns brengen
hun oudertaak atomisch via geldige statusovergangen naar `review`, met begrensde
runprovenance. Afwijzingen blijven actiegericht, review is eenmalig en `done`
vereist nog expliciet resultaat plus verificatienotitie. Oversized bewijs wordt
niet geparseerd. 332 backendtests plus twee subtests en onafhankelijke Python-
review geslaagd. Echte provideruitvoering en capability-isolatie blijven open.

**13 september, servermonitor:** read-only `GET /api/server/status`, connector-
audit en Gaia-kaart toegevoegd. Endpoint accepteert geen caller-paden of
commando's en toont alleen begrensde OS-, uptime-, load-, geheugen-, vaste
schijflabel- en processtatus. Uitgeschakeld betekent geen probe. 328 backendtests
plus twee subtests, 42 webtests, TypeScript/build/lint en lokale browserproef
geslaagd. Doelservermeting en muterende beheeracties blijven open. Zie
[servermonitor](server-monitor.md) en [browserbewijs](server-monitor-browser-evidence.md).

**13 september, self-improvement kern:** geauthenticeerde preview/run-API rond
review-only patchvalidator toegevoegd. Exacte R3-approval bindt opaque tijdelijke
repository, base commit, patchhash, filelijst en statische validatie en wordt
atomisch één keer verbruikt. Een uur expiry/cleanup, concurrentie en
descriptor-relatieve symlink-/renamebescherming zijn getest. Geen gewijzigde
code wordt uitgevoerd; publieke state bevat geen raw patch of paden. Gaia Werk
heeft nu ingeklapte exacte preview/checkbox/run-bediening; browserproef
bevestigt invalidatie na edit, reviewbewijs, bronbehoud en cleanup. Volledige
stand: 345 backendtests plus twee subtests en 46 webtests; Python-, security- en
React-review zonder P1/P2. Volledige self-improvement blijft open tot OS-sandbox,
echte tests en gecontroleerde nachtqueue-integratie aantoonbaar werken. Zie
[sandboxgrens](self-improvement-sandbox.md) en
[browserbewijs](self-improvement-browser-evidence.md).

**12 september, research:** Firecrawl v2 search-only executor, vaste host,
HTTPS/domein/IP-filter, caps, server-side preview-ID/fingerprint met 15 minuten
geldigheid, provider-outcomeaudit en Gaia tweestapsflow toegevoegd. Standaard
uit; geen live call of sleutel gebruikt. 314 backendtests plus twee subtests,
39 webtests, TypeScript/build en browser-disabled-state geslaagd. Live provider-
acceptatie blijft open. Zie [research](research-executor.md) en
[browserbewijs](research-browser-evidence.md).

**12 september, autonomie:** bestaande nachtqueue/value engine/ochtendbrief hergebruikt.
Gaia toont begrensde status en ochtendbrief; vaste veilige bronscan werkt
handmatig en via optionele systemd-timer om 22:00. Scan doet geen provider- of
netwerkverzoek en maakt geen memory/task/cache-records. 305 backendtests plus
twee subtests, 35 webtests, TypeScript/build en browserherstel geslaagd. Live
externe researchacceptatie, muterende nachtacties en self-improvement blijven open. Zie
[autonomiebewijs](autonomy-browser-evidence.md).

**10 september:** Vandaag en Memory gebruiken echte lokale gegevens. Memory
ondersteunt zoeken, bronweergave, toevoegen, corrigeren en verwijderen met reden;
late zoekresultaten kunnen nieuwe verbinding niet overschrijven. 299 backendtests
plus twee subtests, 30 webtests, TypeScript/build en browseracceptatie zijn
geslaagd. Google Agenda/Gmail is gekozen als eerste alleen-lezen connector;
begrensde client, serverroutes en Gaia-UI zijn lokaal gereed; accountverbinding
en live acceptatie blijven open. Zie [acceptatiebewijs](memory-today-browser-evidence.md),
[Google alleen-lezen client](google-readonly.md) en
[Google-browseracceptatie](google-browser-evidence.md).

**9 september:** duurzame Chat, exacte context-/kostenapproval en Gaia-koppeling
zijn toegevoegd; oudere Werk-jobs zijn direct opvraagbaar. Zie [chat.md](chat.md)
en de actuele [handoff](handoff.md) voor verificatie. Installatie, echte Vandaag/
Memory-data, connectors, autonomie en doelhardware blijven afzonderlijke open
acceptatiestappen. Historische meetmomenten hieronder zijn geen actuele
volledigheidsclaim.

**Kostenherstel 8 september:** gevalideerde usage wordt vóór antwoordparsing duurzaam opgeslagen. Gaia-preview plus expliciete approval kan uitsluitend bewezen verbruik reconciliëren; geen antwoord-/taaksucces, geen herhaling en geen bewijsloze budgetvrijgave. 253 backendtests + twee subtests, 16 webtests/build en desktopbrowserproef geslaagd. Echte chat, oudere-jobdetailherstel en alle overige productcriteria blijven open.

**Nieuwste code 8 september:** Gaia-modelinvoer aangesloten: lokale tekst-/kostenpreview, afzonderlijke approval, invalidatie bij edits en herstel van onzekere verzending met dezelfde aanvraag-id. Leesbaar antwoord blijft na herladen beschikbaar. 238 backendtests + twee subtests, 14 webtests en desktopbrowserketen met nepmodel geslaagd. Geen live API-/hardwarebewijs; reconciliatie, echte chat en de oorspronkelijke volledige agentvisie blijven open. Zie [model-work.md](model-work.md).

**Nieuwste code 7 september:** stap 4 heeft nu echte Responses-transportcode en workerintegratie, standaard uit: tekst-/kostenapproval, gedeelde SQLite-reservering, usage-registratie en crashherstel zonder automatische betaalde herhaling. Gaia toont modeljobs met het juiste type/verbruik. Offline bewijs en open grenzen: [model-work.md](model-work.md). Nog geen live provider-/M40-test; Gaia-modelinvoer, reconciliatie en algemene agents blijven open. De oudere updates hieronder zijn historisch bewijs, geen actuele afronding van het volledige product.

**Update 7 september:** REC-01/02/05 bronherstel, aanvullende scan en integratie uitgevoerd; 185 backendtests plus zeven webbridge-tests geslaagd. Stap 2 is ook met echte HTTP/SQLite getest. Stappen 3 en 5 hebben nu één echte lokale verticale integratie: syntaxcontrole met duurzame checkpoints en Gaia-Werk, inclusief pauze/hervatten/annuleren en procescrashregressie. Dit is geen voltooiing van algemene agents. **Volgende code: echte begrensde modeluitvoering met kostenreservering en offline tests**, daarna chat en read-only connectors. Zie local-work.md; de oudere tabellen hieronder blijven de volledige featurecriteria bewaren.

Stand: 6 september 2026. De eigenaar vraagt volledige stapsgewijze uitvoering. **Prototype** is voorbeeldgedrag; **code aanwezig** is geen live integratie. Alleen passende controles rechtvaardigen “werkend”. Zie de [SSD-audit](server-recovery-audit.md) voor het actuele implementatiebewijs.

## Eerst continuïteit herstellen

| ID | Prioriteit | Status | Taak en acceptatiecriterium |
|---|---|---|---|
| REC-01 | P0 | Volledig lokaal hersteld | WSL read-only kopie inclusief .git en privéstate; archiefvergelijking, alle reguliere bestandshashes en git fsck geslaagd. Zie wsl-recovery.md. Volledige bronintegratie/publicatiescan volgt. |
| REC-02 | P0 | Aanvullende inventaris nodig | HEAD `6b1863b`, 16 lokale commits plus dirty werk behouden. Actuele grote server/store/testfiles nu beschikbaar; volledige tests kunnen na veilige integratie starten. |
| REC-03 | P0 | Uitgevoerd en build getest | Bestaande Gaia-frontend behouden in `apps/web`; SHA-256-kopiecontrole en build geslaagd; lint heeft nul errors en vijf bestaande warnings. |
| REC-04 | P0 | Vastgelegd in docs | Maak plan, backlog en Codex-hervatinstructies vindbaar. Verifieer na publicatie de GitHub-commit. |
| REC-05 | P0 | Selectie gecontroleerd | 73 bronbestanden geselecteerd, hashes vastgelegd; twee docs geschoond. Private logs/secrets/runtime uitgesloten. Herhaal bij aanvullende export. |

## Uitvoeringsvolgorde en voltooiingsvoorwaarden

1. **Herstelbasis:** actuele ontbrekende files terughalen, integriteit controleren, volledige bestaande tests uitvoeren. Geen vervangende stack of stilzwijgend terugzetten van oudere code.
2. **Eerlijk uitvoeringsbewijs:** lokale schijntestproducent gecorrigeerd op `codex/night-queue-evidence` (7 regressietests, 34 bestaande route-evals geslaagd). Niet-geïmplementeerde self-improvement blijft review/expliciete fout, nooit tests_passed of fictieve wijziging. Volledige store/HTTP-test en echte geïsoleerde patch/testuitvoerder blijven open; zie [bewijs](night-queue-evidence-repair.md).
3. **Duurzame werkcyclus:** één taak echt uitvoeren met opgeslagen events/checkpoints, herstart/retry/idempotentie en backendapproval voor concrete acties.
4. **Providers:** bestaande router/adapter uitbreiden met echte begrensde uitvoering. OpenAI optioneel en standaard uit totdat model, budget en datascopes gekozen zijn; offline tests vóór betaalde smoke-test. M40-route pas activeren na benchmark.
5. **Gaia verbinden:** bestaand ontwerp behouden; chat/werk/approval/memory koppelen aan werkelijke status. Fouten en mock/demo zichtbaar onderscheiden.
6. **Gecontroleerde autonomie:** nachtqueue, memory/value-engine, research en morning brief met budget, annulering en herstarttests; geen verzonnen resultaten.
7. **Connectors per stuk:** begin read-only; agenda/mail, serverbeheer, shopper, finance en printer vereisen eigen scopes, concrete approvals en regressietests. Externe pakketten pas na licentie-/onderhoud-/veiligheidscontrole.
8. **Ubuntu-oplevering:** reproduceerbare installatie, secretbeheer, healthchecks, private backup/restore, systemd, logrotatie en begrensde resources. Doelserver-preflight en delivery-smoke zijn bewezen op de gemeten M40/9.3-GB-VM; reboot/rollback, Podman-sandbox en fan-failsafe blijven aparte acceptatiechecks.

Releaseklaar betekent relevante acceptatiechecks aantoonbaar geslaagd, geen bekende kritieke veiligheidsfouten, begrensde kosten en herstelbare fouten. Een lokale mocktest bewijst geen werkende dienst of hardware.

## Functionaliteit, bewijs en volgende stap

| Onderdeel | Huidig bewijs | Volgende acceptatiecriterium |
|---|---|---|
| Vandaag / Chat / Werk / Memory | Frontendcode en ontwerp aanwezig | Bestaande vorm behouden; echte backendstatus koppelen zodra API bekend is |
| Langlopende agents | UI-prototype met doel, fases, ETA, team en checkpoints | Een echte taak overleeft workerherstart en browserherladen, hervat vanaf opgeslagen checkpoint en toont verifieerbaar resultaat |
| Voortgang en ETA | Vaste voorbeeldwaarden | Toon werkelijke events; onbekende ETA als onbekend, nooit schijnprecisie of timer als bewijs van werk |
| Automatische/handmatige agentkeuze | UI-prototype | Werkelijke router legt rolkeuze uit; scopes en toolrechten blijven server-side begrensd |
| Memory / routines | Visie en voorbeeldgraph | Duurzame opslag met bron, confidence, correctie en verwijdering; privacyregels toepassen |
| Self-learning | Visie en learning-preview | Gespreks-/foutsignaal produceert herleidbaar voorstel; verbetering wordt getest en is terugdraaibaar |
| Value Engine / toolbouwer | Scoremodel in conceptplan | Keuze uitvoeren, vragen, bewaren of afwijzen met reden, kosten en herbruikbaarheid; geen dubbel backlogitem |
| MCP/plugin discovery | Broncatalogus | Bestaande tools inventariseren; kandidaat beoordelen op onderhoud, permissies en compatibiliteit vóór installatie |
| Nachtcyclus | Gepland om 22:00 | Configureerbare tijdzone Europe/Amsterdam, budget, queue, onderbreken voor livegebruik en ochtendrapport |
| Lokale/externe modelrouter | Hardwarewens en kandidaten | M40-benchmark plus werkende fallback; geen onbewezen model/runtime als verplichte basis |
| Manager / Rabobank / marktdata | Visie | Eerst gecontroleerde read-only koppeling; externe geldacties vereisen specifieke backendapproval |
| Planner / Magister / mail / agenda | Visie, UI-agentrol | Eén echte bron aansluiten; concepten en wijzigingspreview met tijdzone en deduplicatie |
| Shopper / Marktplaats / Vinted / TicketSwap | Visie, UI-agentrol | Shortlist met bron/prijs/tijdstip; bericht, bod of aankoop afzonderlijk autoriseren |
| Server manager, beide servers | Visie, UI-agentrol | Read-only inventaris en periodiek rapport; concrete update-/herstartactie met bewijs en passende approval |
| 3D-referentiemaker | Gebruikerswens, nog geen bewezen pipeline | Zoek bronmodel of bruikbare aanzichten; lever referentiemodel met herkomst, schaal/onnauwkeurigheid en licentie |
| 3D-printermanager / camera / Fluidd | Gebruikerswens, UI-agentrol | Lees telemetrie/camera; meld concrete afwijking; instellingswijzigingen begrenzen en expliciet autoriseren |

De tabel bewaart de oorspronkelijke feature-acceptatiecriteria; de recente implementatie-inventaris staat in de audit. Decision Layer/modelrouter bestaan (34/34 evaluaties); agentrunner is mock, provideradapter dry-run, planner sampledata. Store-/HTTP-functionaliteit is beschreven maar door ontbrekende actuele files niet volledig verifieerbaar. Geen van deze onderdelen hoeft blind vanaf nul gebouwd te worden.

## Eerste verticale integratie na SSD-inventaris

1. Behoud de bestaande backendstack als die bruikbaar is; leg eventuele noodzakelijke afwijking met bewijs vast.
2. Koppel de bestaande Werk-UI aan één duurzame taak: aanmaken, echte stappen/events, pauze, hervatten en afgerond resultaat.
3. Test crash/herstart en dubbele verzoeken, inclusief een pending approval. Uitgevoerde externe acties mogen niet opnieuw worden uitgevoerd door een retry.
4. Sluit daarna één betrouwbare read-only tool aan en breid gericht uit met planner/memory/modelrouting.

## Concrete gebruikersscenario's

- **WK in de agenda:** bron en tijdzone verifiëren, preview tonen, gewenste agenda vaststellen, na autorisatie schrijven; opnieuw uitvoeren maakt geen duplicaten.
- **Reisresearch na vliegtickets/Airbnb-vraag:** optionele achtergrondtaak met budget en bestemming; resultaten, bronnen en datum bewaren; geen boeking uit een informatievraag afleiden.
- **Weer in Amsterdam bij een fout:** fout classificeren, begrensde retries en geschikte fallback; aantoonbaar antwoord leveren of concrete blokkade melden. Een structurele fout maakt een reparatietaak met regressiecontrole.

## Bronnen uit de oorspronkelijke ideeën

De GitHub-kandidaten staan in sectie 22 van het conceptplan. Hun eerdere onderhoudsbeoordelingen zijn niet allemaal opnieuw geverifieerd tijdens deze migratie. Onderstaande videobronnen zijn geregistreerd als inspiratie, nog niet inhoudelijk gecontroleerd:

- https://www.youtube.com/watch?v=AttKv_d7P04
- https://www.youtube.com/watch?v=cQqOkx5qnWo
- https://www.youtube.com/watch?v=19xCOJxWU0A

“Jcode” en “Ollm” moeten nog als exacte projecten worden geïdentificeerd. Colibri is de opgegeven repository `JustVugg/colibri`; de gewenste GLM-versie en compatibiliteit moeten nog worden bevestigd.
