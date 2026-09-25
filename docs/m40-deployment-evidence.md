# Tesla M40 deployment evidence — 21 September 2026

Leon now uses a loopback-only Ollama runtime with `qwen2.5-coder:14b` as its
primary text route. OpenAI remains separately disabled in production and is not
an automatic fallback.

The coding-agent wrapper launches OpenCode with `gpt-oss:20b` through Ollama.
Codex CLI plus this model answered a direct prompt, but its first repository
tool call failed with an unsupported `shell` route. OpenCode successfully
called its `read` tool on `README.md` and returned the actual first line. The
separate `qwen2.5-coder:14b` model serves assistant chat; direct native and
OpenAI-compatible Ollama tool tests showed that it emits JSON tool-call text
instead of a structured tool call, so it is not the coding-agent default.

OpenCode then edited a disposable file from `BEFORE` to `AFTER` and read back
the result. Its exported session records `glob`, `read`, `edit`, and `read`
tools; the file contents were checked on disk and the file was removed. The
wrapper sampled a peak of 80C on this short write trial. The normal project
config asks before edits and shell commands; the smoke test used an inline
edit-only allowance and denied shell commands. Install the pinned CLI/model
with `./scripts/leon-m40-coding-setup`; run it through
`./scripts/leon-m40-coding-agent`. It is an interactive coding CLI, separate
from Leon's still-mock general agent-run endpoint.

## Target-host evidence

- GPU: Tesla M40 24GB, 23,040 MiB reported by `nvidia-smi`.
- Driver: 580.178.04. Ollama selected its CUDA v12 backend for compute
  capability 5.2 and offloaded all 49 model layers.
- Runtime/model: Ollama 0.34.2, Qwen 2.5 Coder 14B Q4_K_M, 4,096-token context.
- Device allocation: about 9.7 GB VRAM during the loaded-model check.
- Bounded coding benchmark: 15.34 output tokens/second. A subsequent warm
  health prompt completed in 1,296 ms.
- First-load overhead is material on this low-RAM VM: the initial load took
  about 55.7 seconds. The service keeps the model warm for ten minutes.

## Quality and cost acceptance

One synthetic comparison asked both the local model and `gpt-5.6-luna` to fix a
one-line function, extract a city, and produce an eight-word-or-shorter summary.
Both passed 3/3 deterministic checks. The local run used 116 prompt and 46
output tokens. The cloud baseline used 89 input and 97 output tokens; Leon's
conservative accounting formula estimates that call at about USD 0.000139.

This is a small deployment acceptance test, not a general quality benchmark.
It supports routing low-risk chat and bounded coding prompts locally. High-risk
decisions still require their existing review and approval controls.

## Chassis-fan boundary

The deployed Linux environment is a KVM guest. It can read the passed-through
GPU temperature, but it has no `hwmon`/PWM device for the physical chassis fan.
The user manages the chassis fan with a shell script on the Proxmox host. Its
posted curve drives the M40's `pwm2` fan to 100% from 68C. The guest
cannot inspect the fan's RPM, PWM mapping, or fancontrol service status. Do not
install a second fan controller in this VM. The coding-agent wrapper reads the
passed-through GPU temperature and stops a run at its configured ceiling; this
is a stop guard, not evidence that the physical fan responds. Verify the fan's
RPM/PWM response on the Proxmox host during a bounded GPU load.

The 75C and 78C guards stopped OpenCode/Qwen tool trials before a file read
completed, even after reducing Ollama context from 32K to 16K. The user then
reversed the fan and explicitly selected an 89C coding-agent ceiling. The
wrapper checks once per second and stops the model at that reading. The
installed driver reports GPU slowdown at 89C and shutdown at 92C, so this is
the driver's slowdown boundary, not a verified sustained operating target.
Sustained cooling still needs a measured host RPM and workload check.

The posted host script sets PWM to 50% when SSH or `nvidia-smi` fails. Since a
running VM could also lose SSH while the GPU is hot, change that fault branch
to PWM 255 and wrap the full SSH command with a short `timeout`. The script's
EXIT trap covers a normal stop, not a host power loss or `SIGKILL`. A corrected
host-side template is in `deploy/proxmox/m40-fan-control.sh`; it has not been
installed on Proxmox from this VM. The user should compare it with the running
host script and verify `fan2_input` actually tracks the M40's fan.
