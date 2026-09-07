# Bewijs

7 september: 185 tests + twee subtests geslaagd, exit 0 (18.40s), Ubuntu/WSL netwerkisolatie. Web: zeven tests, tsc, lint (0 errors/5 bestaande warnings), Node-mode build geslaagd. Browser/Python/SQLite echte keten inclusief pagina reload en afzonderlijke workerprocessen 3/3 bevestigd; alleen tijdelijke state/nepcredential. Zie local-work.md voor scope en reproduceerbare commando's. Eerdere mislukte pogingen: workerlabelargument en illegale test-transitie gecorrigeerd; herstelde watch had een uitvoercollector-race, gereproduceerd met vertraagde tee en aan eigenaar gerepareerd. Geen succesclaims op mislukte runs. Productiedoel blijft needs-verification; geen M40/live-providerbewijs. Gebruikte skills hielden eigenaren klein en claims beperkt; geen ingerichte Aegis-workspace-helper/baseline aanwezig, dus geen structurele-helperclaim.

Inventarisbewijs: docs/server-recovery-audit.md. AST op 22 modules en directe evaluate_cases-set 34/34 geslaagd op Python 3.14. Originele .git fsck meldt één ontbrekende blob; actuele server/store/testfiles ontbreken.

Gedekte scope: aanwezige code-inventaris, beperkte routeringsevaluaties, bronselectie. Ongedekt: volledige server/store-integratie, Ubuntu/M40, live providers, complete recovery. Vertrouwen C voor productgereedheid; geen acceptatie of voltooiing van het product.

Publicatie gecontroleerd met git fetch, tree-inhoud en git ls-remote: main d1948cf5223808d1106671e2187a8268437f03df en herstelbranch 8ebd5a913d91c9c99ccdf82cce00f2df86db66e9. Alle 73 remote bestands-SHA256-hashes en Git-modi komen overeen met manifest; alle 73 originele bronhashes zijn nog ongewijzigd. Exitcode 0. git diff --check en behoud oorspronkelijke plansecties 1–24 geslaagd. De lokale main-werkboom was na synchronisatie schoon. Geen private runtimeback-up.

Aanvullend bewijs: docs/night-queue-evidence-repair.md beschrijft 7/7 scheduler/policy/morning-briefregressies met store-testdouble en 34/34 route-evals. WSL-recovery is volledig lokaal geverifieerd; de eerdere ontbrekende files/objecten zijn terug. Nu volgt de volledige testset met echte tijdelijke SQLite en loopback-HTTP.
