# WSL-herstelcheckpoint — 6 september 2026

De eigenaar meldt dat DiskGenius de grote bestanden niet kopieert en heeft gevraagd WSL te proberen.

## Herstel geslaagd na herstart

- Windows is op 6 september om 21:16 opnieuw gestart; pending reboot verdwenen.
- Ubuntu 26.04 LTS is geïnstalleerd en gestart onder WSL2, kernel 6.18.33.2-microsoft-standard-WSL2. Dit is de lokale ontwikkelomgeving, niet de Tesla-server.
- usbipd-win 5.3.0 geïnstalleerd vanuit de officiële release; SHA256 gecontroleerd tegen winget-metadata en Authenticode-handtekening geldig. Eerste MSI-poging met slashpad faalde (1619); hetzelfde bestand met native Windows-pad installeerde met exitcode 0.
- Alleen de geverifieerde Crucial-USB-bridge is doorgegeven. Firewall tijdelijk beperkt tot het concrete WSL-IP; geen andere USB-apparaten gedeeld.
- Hoofdpartitie geïdentificeerd als ext4. Hele blockdevice en partitie read-only gezet; mountopties `ro,noload`, door findmnt bevestigd als `ro,relatime,norecovery`.
- Oorspronkelijke paden: `/home/per/leon-ai-assistant` en `/home/per/leon-workspace`. Beide volledig gearchiveerd en uitgepakt in `C:/Users/perhorst/Documents/leon-ssd-full-2026-09-06`. Eerdere exports niet overschreven.
- Archief `leon-ssd-original.tar` bevat ook credentials, logs en database: **uitsluitend privé bewaren, nooit GitHub**. Het archief bewaart Linuxmetadata. SHA256: `4e030ce728a54fdd3d833d9e3b555a6cc575e76a0f35e221bac477871bd2ee2a`.
- `tar --compare` tegen de SSD geslaagd; alle reguliere bestanden van de uitgepakte kopie met SHA256 tegen de read-only SSD gecontroleerd. Geen verschillen.
- `git fsck --full --no-reflogs --no-dangling` op de volledige kopie: exitcode 0, geen meldingen. HEAD blijft `6b1863b6e1fdc612672c816ac048313c677115ca`; ongecommitte wijzigingen behouden.
- Alle 73 eerder geselecteerde bronbestanden hebben dezelfde oorspronkelijke hashes. Teruggevonden actuele files: server.py 221.460 bytes, store.py 381.378 bytes, test_control_plane.py 229.210 bytes, conceptplan 84.555 bytes. SQLite-database 794.624 bytes is privé meegekopieerd; nog geen logische restore/integriteitstest uitgevoerd.
- Na controle: bestandssysteem unmounted, USB detached en unbound. usbipd-service gestopt en op Manual gezet; bijbehorende firewallregel uitgeschakeld. Geen actieve of persistente USB-sharing meer.

## Eerstvolgende ontwikkelstap

Werk niet in het originele archief of de uitgepakte recoverybron. Vul een aparte gecontroleerde ontwikkelkopie aan met de actuele bron, behoud de nachtqueue-reparatie, scan nieuw te publiceren bestanden op secrets en vergelijk het serverplan met main. Draai daarna de volledige oorspronkelijke tests met tijdelijke state en zonder echte credentials/providercalls. GitHub bevat op dit checkpoint nog de gedeeltelijke bron plus reparatie, niet de nieuw teruggevonden grote files.

## Historisch: status vóór herstart

- WSL 2.7.13.0 geïnstalleerd. Windows Installer rapporteert succes (status 0); wsl --version werkt, kernelversie 6.18.33.2-2.
- VirtualMachinePlatform ingeschakeld door de installer. DISM meldt op 21:12:23 Europe/Amsterdam: reboot required=yes; herstart is onderdrukt met /NoRestart.
- wsl --status: standaardversie 2, maar WSL2 kan vóór herstart nog niet starten. Deze generieke virtualisatiemelding bewijst nu geen BIOS-probleem; eerst herstarten. De eerdere firmwarecheck gaf VirtualizationFirmwareEnabled=True.
- wsl --list --verbose: nog geen Linuxdistributie geïnstalleerd. Ubuntu-installatie is dus niet voltooid.
- Geen SSD-mount, schijfreparatie of wijziging van de bronbestanden uitgevoerd. usbipd is nog niet geïnstalleerd.

## Hervatten na handmatige Windows-herstart

1. Controleer wsl --status, wsl --version en wsl --list --verbose. Installeer/initieer Ubuntu alleen als nog afwezig; geen bestaande distributie unregisteren.
2. Controleer WSL2-start voordat SSD-doorgifte wordt geprobeerd. Heridentificeer de Crucial CT525MX300SSD1 op model/capaciteit en USB-apparaat; PhysicalDrive2 is geen stabiel nummer.
3. Microsoft vermeldt dat wsl --mount USB-schijven niet rechtstreeks ondersteunt. Onderzoek usbipd-win voor USB-doorgifte, met alleen het juiste apparaat geselecteerd. Houd rekening met installatierechten, service/firewall en eventuele mass-storage-kernelondersteuning; geen brede USB-sharing aanzetten.
4. Sluit DiskGenius en andere schijftoegang voordat het USB-apparaat exclusief wordt gekoppeld. Identificeer in Linux eerst partitietype/LVM/encryptie. Mount alleen-lezen met bestandssysteemgeschikte opties, zonder journalreplay waar nodig; niet blind ext4 of een devicepad aannemen.
5. Kopieer de volledige projectmap inclusief verborgen .git naar een nieuwe herstelmap, behoud eerdere exports en private gegevens lokaal. Vergelijk hashes en git fsck. Actuele server.py, store.py, test_control_plane.py en plan ontbreken nog in de eerdere export.

## Documentatie

- [Microsoft: WSL installeren](https://learn.microsoft.com/en-us/windows/wsl/install)
- [Microsoft: Linux-schijf koppelen en USB-beperkingen](https://learn.microsoft.com/en-us/windows/wsl/wsl2-mount-disk)
- [Microsoft: USB-doorgifte met usbipd](https://learn.microsoft.com/en-us/windows/wsl/connect-usb)

Dit checkpoint is installatie-/herstelvoortgang, geen bewijs van complete codebackup of werkende Leon-backend.
