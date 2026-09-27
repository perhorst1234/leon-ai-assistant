# Magister-agenda

Eigenaarbediening: Vandaag → Je agenda → Magister koppelen. Een geverifieerde
verbinding toont schoolagenda; handmatige knop haalt komende7dagen op, eerste
zes compact, volledig overzicht via chat. Bijvoorbeeld “Toon mijn Magister-
agenda morgen” of “Zoek vrije momenten deze week, minstens60minuten”.

Bron is de bestaande serverbrowser op eigen ingestelde vova-schoolportal.
Native Angular HTTP-client houdt de bestaande sessie binnen de browser.
Account + leerlingnummer worden gecontroleerd voordat afspraken worden gelezen.
Alleen status1-afspraken; maximaal7dagen/50records. Id, titel, begin/eind en
locatie, geen volledige leerlinggegevens/geboortedatum/huiswerk/berichten.
Geen nieuwe Magister-token/wachtwoordexport of modelcall nodig voor schoolread.
Een huidige geldige sessie is vereist; bij volgende aanmelding kan het bestaande
wachtwoord-/Authenticator-/codeformulier nodig zijn. Geen MFA-bypass.

Privé LEON_MAGISTER_AGENDA_ENABLED=1 neemt de lessen ook mee naast primaire
Google-agenda bij vrije momenten. Bij ontbrekende/afgekapte schoolbron worden
geen vrije momenten bevestigd. Datetimes moeten offsets hebben; geldige
intervallen/gevraagde overlap worden gecontroleerd. Datapad is alleen-lezen;
Google-afspraken beheren blijft de aparte eigen-agendawriter.

Doelserver27september: eigen account gecontroleerd; schoolAPI200/18weekitems,
backend+webbridge200, echte beide chatantwoorden; planner7slots zonder lesoverlap.
Vandaag connected/6schoolitems daadwerkelijk gerenderd. Voor browseracceptatie
tijdelijke lokale Leon-testsessie, oorspronkelijke cookie hersteld; geen
wachtwoord veranderd. Het complete schoolrooster blijft privé. Code+tests
alleen; geen schooldata of browserprofielen in openbare repository.

668full backend/56gerichte checks,57webtests, TypeScript/build, lint0errors en7
bestaande warnings. Cijfers/huiswerk/schoolmail/routines en echte nieuwe password/
MFA-aanmelding blijven afzonderlijk te bouwen of te bewijzen.
