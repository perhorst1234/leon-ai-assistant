# Nachtqueue: eerlijk testbewijs

Update 7 september: volledige store/server/tests zijn geïntegreerd. De store registreert aangeleverd bewijs maar past zelf geen patch toe en draait geen tests; de eerdere tegenhypothese is dus verworpen. De oorspronkelijke fictieve-succestest is gecorrigeerd, HTTP/SQLite-regressie toegevoegd. Volledige suite: 185 tests + twee subtests geslaagd. De lokale worker uit local-work.md is een afzonderlijke echte read-only broncontrole, geen self-improvementuitvoerder.

## Afbakening

Parent: uitvoeringsbacklog stap 2. Dit is een begrensde veiligheidsreparatie, niet de voltooiing van self-improvement of de backend. Snapshotbranch blijft ongewijzigd; ontwikkelbranch: codex/night-queue-evidence vanaf 8ebd5a9. Startwerkboom schoon; geen externe acties of live state. Main was 4ae3e10.

Change Necessity: code-change. Alleen documentatie voorkomt niet dat run_once met toegestane R3 een verzonnen succes boekt. Minimale eigenaar is night_queue.py: verwijder vooraf verzonnen bewijs en de interne actie die een patch/testsucces fabriceert. Behoud action-ID, reviewvoorstellen, bestaande policy-API en andere acties. Geen test-/patchuitvoerder erbij verzinnen zolang actuele store/server/testbron ontbreekt.

TDD Mode off / Decision skipped; diagnostische reproductie en gerichte regressietests blijven verplicht. Geen strict-TDD-claim.

## Diagnose en contract

De scheduler produceert zelf zowel tests_passed=True als de vaste passed/exit_code=0-output. De policy vertrouwt die metadata; run_once laat de actie toe wanneer R3 in allowed_risk_classes staat. Default R1/R2 blokkeert dit al, maar is geen bewijs dat de R3-uitvoering klopt. De directe interne actie kan dezelfde verzonnen output produceren zonder policy.

CanonicalOwner: scheduler als bewijsproducent. PatchShape: verwijder synthetisch resultaat, gebruik bestaande policyblokkade en expliciete niet-geïmplementeerde uitvoering. Topologie: één lokale bewijsfout met policy- en rapportagegevolgen. Die lokale oorzaak is bevestigd; de bredere store/HTTP-keten blijft onbekend wegens ontbrekende actuele bron. Geen systeemwijde root-cause- of veiligheidsclaim.

Sterkste tegenhypothese: record_controlled_self_improvement zou zelf echt werk kunnen uitvoeren. Dit kan de vóór die call verzonnen testclaim niet rechtvaardigen; actuele store ontbreekt, dus integratie blijft te controleren.

Verificatie: R1/R2 en expliciet R3/R4/R5 blijven zonder testbewijs geblokkeerd; directe of geforceerde uitvoering kan geen succesvolle wijziging boeken; read-only indexactie blijft werken. Controleer echte policy, scheduler en morning-briefcompositie samen met een store-testdouble. Dat testdouble is alleen een grens voor ontbrekende persistence, geen backendtestbewijs.

## Complexiteit en verwijdering

Lokaal herstel zonder nieuwe verantwoordelijkheid: vervang circa 60 regels synthetische uitvoering door expliciete onbeschikbaarheid. Store-import wordt alleen voor typechecking gebruikt omdat uitsluitend een annotatie hem nodig heeft. Eén unittestbestand van beperkte omvang; geen nieuwe dependencies.

Anti-entropy: code-retirement/delete-first van fictief bewijs in de interne scheduler; action-ID en echte review/rapportagerol blijven. Geen schema/API- of databasedeletie, originele export en snapshot intact. Dit is omkeerbaar Git-bronwerk binnen de gevraagde implementatie, geen destructieve runtimeactie.

Volledige self-improvement blijft open: echte geïsoleerde patch, vastgelegde bronversie/hash, begrensde testuitvoering, gemeten resultaat, approval/rollback en crash-/herstarttests. Pas daarna mag deze actie daadwerkelijk uitvoeren.

## Uitgevoerde controles

- Python 3.14: `PYTHONPATH=src python -B -m unittest discover -s tests -p test_night_queue_evidence.py -v`: 7/7 geslaagd.
- Diagnostische vergelijking met oorspronkelijke scheduler op 8ebd5a9: dezelfde zeven tests leveren zes failure-assertions op (één test heeft twee subcases), nul testerrors. Alleen de annotatie-import van de ontbrekende store werd in deze in-memory vergelijking weggelaten. Geen bronbestand teruggezet. Eerste diagnostische wrapper verwachtte vijf assertions en eindigde daardoor met exitcode 1; gecorrigeerde telling bevestigt zes, zonder productiecode aan te passen.
- `evaluate_cases(load_eval_cases())`: 34/34, nul safety failures; 23 aanwezige bron/testfiles AST-gecontroleerd.
- `git diff --check`: geslaagd. Geen extra dependency, providercall, echte patch of databasewrite.
- Confidence B voor deze lokale veiligheidsreparatie; C voor volledige productgereedheid. Echte store/HTTP-compatibiliteit en historische tests kunnen pas na complete export worden getoetst.
