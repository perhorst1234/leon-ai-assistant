# Duurzame chat

Chat gebruikt de bestaande Python/SQLite-backend en begrensde modelworker.
Gesprekken en berichten blijven na herladen bewaard. Zonder modelconfiguratie
ontstaat geen fictief antwoord: de UI toont de werkelijke uitvoeringsstatus.

## Gebruik

Start backend, worker en web volgens [local-work.md](local-work.md). Open Chat,
kies Verbonden chat en verbind met je dashboardtoken. Het token blijft in het
geheugen van de weergave; na herladen verbind je opnieuw. Open een gesprek of
begin een nieuw gesprek. Bekijk vóór verzending de volledige context en de
output-/kostengrenzen. Goedkeuring staat nooit vooraf aangevinkt.

De preview bevat begrensde eerdere berichten plus het huidige bericht. De
server bindt de goedkeuring aan de exacte tekst én beide grenzen. Een wijziging
of inmiddels veranderde context vraagt een nieuwe preview. Er is geen algemene
tooluitvoering, onbeperkte fallback of automatische betaalde herhaling.

## Opslag en herstel

- Gesprekken en berichten staan in eigen SQLite-tabellen, los van de lijst met
  de honderd nieuwste werkjobs. Gesprekken zijn gepagineerd opvraagbaar.
- Een aanvraag-UUID wordt aan de precieze tekst, context en grenzen gebonden.
  Herstel mag uitsluitend dezelfde goedgekeurde queue-opdracht terugvinden.
- De UI toont pending, complete, error en unknown. Een antwoord verschijnt
  uitsluitend uit een succesvol opgeslagen modelresultaat.
- Gelijktijdige verzending wordt transactioneel gecontroleerd. Verouderde
  context en hergebruik van een UUID voor andere inhoud worden geweigerd.
- Modelkosten en onzekere uitkomsten volgen [model-work.md](model-work.md).

## Verificatie

Browserketen geslaagd met tijdelijke SQLite en nepmodel: nieuwe chat,
preview/goedkeuring, vervallen approval na wijziging, behoud tijdens polling,
antwoord, herladen/opnieuw verbinden en vervolgbericht met eerdere context.
Zie [browserbewijs](chat-browser-evidence.md).

Offline regressies staan in `tests/test_chat_api.py`; proxyregressies in
`apps/web/tests/leon-proxy.test.mjs`. De handoff bewaart de actuele gecombineerde
testresultaten. `tests/ui_model_fixture.py` gebruikt uitsluitend tijdelijke
SQLite, een synthetisch token en een nepmodel voor browsercontrole.

Geen echte providercall, gebruikerssleutel, betaling of doelhardware is met
deze fixture getest. Volledige productacceptatie blijft open; zie
[completion-plan.md](completion-plan.md).
