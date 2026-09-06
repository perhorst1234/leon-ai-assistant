# WSL-herstelcheckpoint — 6 september 2026

De eigenaar meldt dat DiskGenius de grote bestanden niet kopieert en heeft gevraagd WSL te proberen.

## Gemeten status na beheerdersgoedkeuring

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
