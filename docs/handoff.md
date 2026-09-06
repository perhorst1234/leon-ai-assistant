# Overdracht — Leon AI Assistant / Gaia

Laatste inventaris: **6 september 2026**. Doel: op Windows verder kunnen werken terwijl de Linux-server wordt geüpgraded, en later met Codex op de server hervatten vanuit GitHub.

## Feiten en herkomst

| Bron | Bevinding | Zekerheid |
|---|---|---|
| GitHub main `d0f7ba0a99227c37fef6c67cc1948d270217ac8a` vóór deze overdracht | Alleen `.gitkeep` en het conceptplan van 2.131 regels; zes commits in de geschiedenis | Direct met Git gecontroleerd |
| Andere remote branch `codex/ontwikkel-volledige-pipeline-voor-ai-assistent` | Verwijst naar `d859bec`, een eerdere planversie | Branchverwijzing en commitgeschiedenis gecontroleerd |
| Codex-taak “Maak AI-assistantwebsite prachtig” | Uitgewerkte frontend, volgens die taak gebouwd/gecontroleerd en privé gepubliceerd op 28 augustus | Taak gelezen; historische testclaims zijn geen nieuwe test |
| Lokale websitebron, commit `f5e8426` | React/Vinext-front-end met synthetische data; werkboom schoon bij inspectie | Broncode, packagebestand en PRODUCT.md bekeken |
| `apps/web` | Kopie van 15 bron-, config-, lock- en assetbestanden, afzonderlijk op SHA-256 vergeleken | Gelijke inhoud bij import; extra README en lokale hostingplaceholder toegevoegd |
| USB-SSD | Crucial CT525MX300SSD1, circa 489 GiB; systeempartitie circa 1 GiB en onbekende hoofdpartitie circa 488 GiB | Windows-schijfinventaris en DiskGenius-scherm |
| Backend op SSD | Eigenaar zegt dat er veel werk is gedaan | Nog niet gelezen; geen uitspraken over ontbrekende of werkende backend |

Leon is de repository/projectnaam; Gaia is de naam van de bestaande frontend en het conceptplan. Er is geen naamswijziging uitgevoerd.

## Huidige blokkade: servercode uitlezen

De schijf was tijdens deze sessie `PhysicalDrive2`. Controleer dit bij opnieuw aansluiten; schijfnummers zijn niet stabiel. De hoofdpartitie begon op offset 1.128.267.776 en had een omvang van 523.982.864.384 bytes. “GPT: Unknown” identificeert het bestandssysteem niet als ext4; encryptie/LVM zijn nog niet onderzocht.

Windows weigert directe leestoegang vanuit de huidige niet-verhoogde Codex-sessie. WSL is niet geïnstalleerd. DiskGenius is aanwezig en door de gebruiker geopend, maar de computerbediening kan het verhoogde venster wel zien en niet bedienen. De gebruiker is gevraagd de hoofdpartitie en de Files-weergave te openen.

WSL kan later een ontwikkelomgeving zijn, maar installatie alleen bewijst geen USB-schijftoegang: [Microsoft documenteert beperkingen van `wsl --mount` voor USB](https://learn.microsoft.com/en-us/windows/wsl/wsl2-mount-disk).

## Eerstvolgende actie

Vind met de leesbare Linux-mapweergave `leon-ai-assistant`. Kopieer de projectmap inclusief verborgen `.git` naar een afzonderlijke lokale recoverymap. Leg het werkelijke Linux-pad vast; `/home`, `/opt`, `/srv` en `/root` zijn alleen zoekkandidaten. Voer geen format-, repair- of partitioneringsactie uit om alleen bestanden te kunnen lezen.

Na herstel:

1. Inspecteer eventuele `AGENTS.md`, Git-status, HEAD, branches en remotes voordat iets wordt uitgevoerd.
2. Bewaar dirty en untracked werk en bepaal welke verschillen niet op GitHub staan.
3. Lees README, package-/dependencybestanden, containers, services, migraties, tests en bestaande werkplannen. Bekijk geen credentialinhoud in uitvoer.
4. Werk de backlog bij met bewezen functies en voer de passende bestaande controles uit.
5. Voeg alleen gecontroleerde broncode toe aan GitHub. Bewaar private configuratie, databases en runtimegegevens afzonderlijk.

## Werkwijze om op een andere computer te hervatten

Begin op de server met inspectie van de bestaande werkmap; trek niet blind een nieuwe versie over lokale wijzigingen heen. In een nieuwe map kan de repository normaal worden gekloond. Lees vervolgens deze handoff, de backlog en het hardwaredocument.

Per betekenisvolle werksessie: noteer doel, gewijzigde bestanden, uitgevoerde controles met uitkomsten, open problemen, huidige branch/commit en de concrete volgende stap; commit code en documentatie samen; synchroniseer met GitHub en controleer de remote-commit. Meld expliciet als synchronisatie niet lukt.

GitHub kan de ontwikkelcontext overdragen. Voor echte hervatting van draaiende agents zijn daarnaast duurzame taakstatus, checkpoints, events, secretbeheer en een private databasemigratie/back-up nodig. Dat is nog een te valideren backendfunctie.

## Controles in deze sessie

- Schijfmodel/capaciteit, niet-verhoogde Windows-rechten en WSL-afwezigheid vastgesteld.
- GitHub-HEAD, branches, geschiedenis en bestandslijst gecontroleerd.
- Website-taak gelezen; websitebron en mockgedrag onderzocht.
- Vijftien frontendbestanden bij kopiëren byte-voor-byte gecontroleerd.
- `npm ci --no-audit --no-fund`: geslaagd, 495 packages geïnstalleerd op Node 24.14.1 / npm 11.11.0. npm meldt dat de vastgelegde ESLint-versie niet meer wordt ondersteund; er zijn in deze bronoverdracht geen dependency-upgrades uitgevoerd.
- `npm run lint`: exitcode 0, geen errors; vijf bestaande ongebruikte symbolen (`Clock3`, `Rocket`, `Search`, `Zap`, `spaceCopy`) geven waarschuwingen.
- `npm run build`: exitcode 0; alle vijf Vinext-buildfasen geslaagd. De bestaande Vinext-beta meldt de routeclassificatie als onbekend. Geen nieuwe browsertest of live deployment uitgevoerd.
- Bestaande plansecties 1–24 ongewijzigd vergeleken met `d0f7ba0`; relatieve documentatielinks gecontroleerd; `git diff --check` geslaagd.
- Gerichte scan op veelvoorkomende private-key- en tokenpatronen in de te publiceren bron/documentatie gaf geen treffers; dit is geen volledige security-audit. De oorspronkelijke deploymentidentiteit en werkmapmetadata zijn niet gekopieerd.
- GitHub-publicatie: deze overdracht gaat als één opvolgcommit op `main`, met behoud van de bestaande geschiedenis. De ontvangende sessie controleert de actuele commit en lokale Git-status; nog niet herstelde SSD-code valt buiten deze publicatie.
- Geen backend- of M40-runtimecontrole mogelijk voordat SSD/server toegankelijk is.

## Gewenste eerste echte verbetering

Na SSD-inventaris: sluit de bestaande Werk-cockpit aan op één echte, duurzame taak met voortgang, checkpoints en hervatten. Hergebruik bestaande backendonderdelen waar mogelijk. Zie [backlog](implementation-backlog.md) voor acceptatiecriteria en de overige oorspronkelijke ideeën.
