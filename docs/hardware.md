# Doelhardware en modelvalidatie

Vastgelegd op 6 september 2026. De server is tijdelijk buiten gebruik tijdens een upgrade.

| Onderdeel | Bekend | Nog controleren |
|---|---|---|
| GPU | NVIDIA Tesla M40, opgegeven door eigenaar | Werkelijke VRAM-capaciteit, aantal GPU's, driver, temperatuur en koeling |
| CPU | Intel Xeon E5-2676 v3, opgegeven door eigenaar | CPU-aantal, RAM, belasting en beschikbare instructies op doel-OS |
| Project-SSD | Crucial CT525MX300SSD1; Windows meldt 525.110.100.480 bytes, circa 489 GiB | Linux-bestandssysteem, projectlocatie, eventuele encryptie/LVM |
| Software | Nog niet geïnventariseerd op server | Linux-versie, containers, modelruntime, modellen en bestaande services |

## GPU-voorwaarden

NVIDIA vermeldt de M40 bij compute capability **5.2 (Maxwell)**. De NVIDIA-compatibiliteitsmatrix vermeldt CUDA 12.x als laatste toolkitfamilie voor Maxwell; kies dus geen willekeurige nieuwste CUDA-image. Een passende toolkit garandeert nog geen ondersteuning door een modelruntime of vooraf gebouwde library.

Bronnen, gecontroleerd op 6 september 2026:

- [NVIDIA legacy GPU-tabel](https://developer.nvidia.com/cuda/gpus/legacy)
- [NVIDIA toolkit-, driver- en architectuurmatrix](https://docs.nvidia.com/datacenter/tesla/drivers/cuda-toolkit-driver-and-architecture-matrix.html)

Ollama, llama.cpp, vLLM, Colibri en andere namen in het conceptplan zijn evaluatiekandidaten. Er is hier nog geen geschikte versie, modelgrootte of snelheid op de M40 bewezen. De gebruikerswens “GLM 5.2 met Colibri” blijft een te valideren model/runtime-combinatie; geen toezegging dat dit model lokaal past of ondersteund wordt.

## Eerst vaststellen zodra de server beschikbaar is

Lees hardware en software uit met onder andere `nvidia-smi`, `lscpu`, `free -h`, `lsblk -f` en de aanwezige runtime-/containerconfiguratie. Bewaar alleen de relevante, geschoonde resultaten in dit document. Controleer eerst de SSD-code op al gemaakte runtimekeuzes.

Een modelproef moet de modelnaam, quantisatie, runtimecommit/versie, driver/toolkit, contextlengte, piek-VRAM, time-to-first-token, tokens/seconde en tool-callkwaliteit vastleggen. Zonder deze metingen is de GPU-route experimenteel.

## Eisen aan de aparte modelplanner

- Dagelijkse chat krijgt voorrang op nachtelijke achtergrondtaken.
- Reserveer geheugen voor gewichten, context/KV-cache en runtime-overhead.
- Begin conservatief met één zware GPU-taak tegelijk; verhoog parallelisme alleen na metingen.
- Ondersteun laden, ontladen, wachtrij, annuleren, time-outs en hervatten via opgeslagen taakstatus.
- Handel onvoldoende geheugen af met lagere context, een kleiner geschikt model, CPU-route of een toegestane externe provider.
- Externe routes moeten privacy, budget en gebruikersautorisatie meenemen.
- Verifieer dat herstarten of modelwisselen geen dubbele externe acties veroorzaakt.
