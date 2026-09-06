# Local GPU/model runtime readiness

Datum: 2026-08-01  
Taak: `task-local-gpu-model-runtime-readiness`  
Status: readiness vastgelegd; geen driverinstall, geen backendinstall, geen modeldownload, geen GPU-run.

## PM-besluit

Leon blijft bruikbaar zonder GPU. De lokale GPU-route wordt pas actief als er bewijs is voor:

1. GPU-detectie;
2. stabiele NVIDIA-driver;
3. backend-healthcheck;
4. kleine quantized modelbenchmark;
5. realistische Leon-taakbenchmark;
6. fallback naar CPU/cloud;
7. redacted benchmarklog in de dashboard/audit-laag.

Daarom is `local_gpu.enabled=false` gebleven in `config/model-routing.json`. De router accepteert `--local-gpu-ready` niet meer als voldoende bewijs; `local_gpu.readiness_status` moet eerst `validated` zijn.

## Lokale inventaris nu

Uitgevoerd als read-only hardware-inventaris:

- `nvidia-smi`: niet aanwezig/geen output.
- `lspci`: alleen Intel integrated graphics zichtbaar, geen NVIDIA GPU.
- RAM: 14 GiB totaal, 9.1 GiB beschikbaar.
- Swap: 4.0 GiB totaal, praktisch volledig gebruikt.
- Schijf: 204 GiB vrij op `/`.
- OS/kernel: Linux `7.0.0-15-generic` x86_64.

Conclusie: nu geen lokale GPU-benchmark draaien. Eerste echte runtime-stap kan pas na fysieke GPU-installatie en approval voor driver/backend/model/benchmark.

## Hardwarematrix

| Target | Compute capability | VRAM/power | Backend-fit | Besluit |
| --- | ---: | --- | --- | --- |
| Tesla M40 | 5.2 | M40 bestaat als 12 GB en 24 GB variant; 24 GB datasheet noemt 250 W en passive cooling | `llama.cpp` waarschijnlijk beste eerste backend; Ollama mogelijk als driver voldoet; vLLM valt af | Experimenteel. Alleen kopen/gebruiken als power/cooling/driver-risico acceptabel is en prijs dit rechtvaardigt. |
| Tesla P40 | 6.1 | 24 GB GDDR5, 250 W, passive cooling | `llama.cpp` en Ollama realistischer; vLLM valt af | Praktischer dan M40 voor oude Tesla-route door 24 GB VRAM en Pascal/INT8, maar nog steeds oud en thermisch kritisch. |
| Andere NVIDIA GPU | afhankelijk | afhankelijk | Als compute capability >= 7.5 wordt vLLM pas realistisch; voor eenvoud blijven Ollama/llama.cpp eerste kandidaten | Bij upgrade voorkeur voor moderne kaart met actieve koeling, voldoende VRAM en actuele driverstack. |

Bronnen:

- NVIDIA legacy compute capability: M40 = 5.2, P40 = 6.1.
- Ollama hardware support: NVIDIA compute capability 5.0+; CC 5.0-6.2 vereist nieuwere driver.
- vLLM stable GPU docs: NVIDIA compute capability 7.5+.
- NVIDIA P40 product brief: 24 GB GDDR5, 250 W, passive cooling.
- NVIDIA M40 24 GB datasheet: 24 GB GDDR5, 250 W, passive cooling.

## Backendkeuze

### Eerste keuze: llama.cpp

Waarom:

- Beste controle over GGUF/quantized modellen.
- Kan CPU en CUDA-routes ondersteunen.
- Biedt CUDA buildopties, inclusief non-native builds en expliciete compute capability selectie.
- Praktischer bij oude of beperkte hardware dan een high-throughput serverstack.

Niet doen zonder approval:

- repo/build installeren;
- CUDA toolkit installeren;
- model downloaden;
- langdurige benchmark draaien;
- modelserver publiek/tailnet exposen.

### Tweede keuze: Ollama

Waarom:

- Simpelste operatorervaring voor lokale modellen.
- Goede kandidaat voor Leon’s modelrouter als healthcheck/API later stabiel is.
- Officiële docs noemen ondersteuning voor NVIDIA CC 5.0+.

Risico:

- Model pulls kunnen snel groot worden.
- Service mag niet publiek openstaan.
- Voor M40/P40 valt dit onder oude CC 5.0-6.2 route en vereist dus drivercontrole.

### Hold: ExLlamaV2

Waarom:

- Interessant voor snelle inference op moderne consumer GPUs.
- Niet nodig vóór baselines met llama.cpp/Ollama.

### Hold/modern-only: vLLM

Waarom:

- Sterk voor high-throughput serving op moderne GPU’s.
- Huidige stable docs vereisen NVIDIA compute capability 7.5+. Dat sluit M40 en P40 uit.

## VRAM/resource policy

Tot validatie:

- `local_gpu.enabled=false`
- `local_gpu.readiness_status=not_validated`
- geen high-risk/critical reasoning op lokale GPU;
- geen modeldownload zonder approval;
- geen GPU-heavy job zonder approval;
- geen public model server;
- geen Tailscale-exposure van modelserver zonder aparte approval.

Eerste goedgekeurde benchmark mag maximaal:

- één kleine quantized testmodelroute;
- één backend tegelijk;
- één GPU tegelijk;
- maximaal 5 GPU-minuten zonder nieuwe approval;
- alleen redacted prompt/response metadata in logs;
- geen privédata in benchmarkprompts.

Stopcriteria:

- `nvidia-smi` toont thermal throttling, error state of onstabiele driver;
- VRAM OOM;
- swap blijft vol of systeem wordt merkbaar instabiel;
- model outputkwaliteit is onvoldoende voor simpele classificatie/samenvatting;
- fallback naar cloud/CPU faalt;
- backend opent een netwerkservice buiten localhost.

## Validated-backend definitie

Een backend is pas validated als deze evidence in het dashboard/auditbaar is:

- GPU exact geïdentificeerd: model, VRAM, compute capability.
- Driver exact geïdentificeerd: versie, CUDA runtime compatibility.
- Backend exact geïdentificeerd: naam, versie/commit, installwijze.
- Model exact geïdentificeerd: naam, quantization, grootte, bron, opslagpad.
- Healthcheck pass: server/CLI reageert lokaal.
- Benchmark pass: realistische Leon microtaken met tokens/sec, latency, memory, VRAM.
- Fallback pass: modelrouter valt terug naar cloud/CPU bij lokale fout.
- Kosten/resource review pass: downloadgrootte, schijf, stroom, thermals.
- Security pass: geen secretwaarden in logs, geen public server, geen ongeautoriseerde tool/file access.

## Concrete benchmarkplan later

Pas na approval:

1. Hardware detectie:
   - `lspci | grep -i nvidia`
   - `nvidia-smi`
2. Driver/CUDA check:
   - driver version;
   - CUDA runtime compatibility;
   - compute capability uit NVIDIA tabel.
3. Backend health:
   - eerst llama.cpp of Ollama, niet beide tegelijk;
   - alleen localhost;
   - geen modelserver naar Tailscale/public.
4. Kleine modeltest:
   - quantized model onder goedgekeurde downloadlimiet;
   - korte synthetic prompts zonder privédata.
5. Leon microtaken:
   - classificatie;
   - korte samenvatting;
   - eenvoudige JSON extractie;
   - fallbacktest.
6. Router update:
   - alleen als benchmark pass;
   - `enabled=true`;
   - `readiness_status=validated`;
   - `selected_backend` en `selected_model` invullen;
   - audit event opnemen.

## Approval blockers

Deze acties blijven geblokkeerd tot expliciete gebruikerstoestemming:

- NVIDIA driver/CUDA installeren of wijzigen.
- Ollama, llama.cpp, ExLlamaV2, vLLM, Docker of services installeren/starten.
- Elk model downloaden.
- Elke GPU-heavy benchmark of run.
- Een modelserver via Tailscale/public beschikbaar maken.
- `local_gpu.enabled=true` of `readiness_status=validated` zetten.
- Nieuwe externe provider/API/secrets toevoegen.

## Dashboardstatus

De volgende candidates staan in de toolcatalogus/dashboardstore:

- `ollama-candidate`
- `llama-cpp-candidate`
- `vllm-candidate`
- `exllamav2-candidate`

Allemaal blijven `candidate` en high-risk/resource-gated.
