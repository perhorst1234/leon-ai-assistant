#!/usr/bin/env bash
# Run on the Proxmox host, not in the Leon VM. Set M40_VM_SSH_TARGET in the
# host service environment (for example, a dedicated read-only SSH account).
set -euo pipefail

: "${M40_VM_SSH_TARGET:?Set M40_VM_SSH_TARGET to the Leon VM SSH target}"

hwmon=""
for candidate in /sys/class/hwmon/hwmon*; do
  if [[ $(cat "$candidate/name" 2>/dev/null || true) == nct6793 ]]; then
    hwmon="$candidate"
    break
  fi
done
if [[ -z "$hwmon" ]]; then
  echo "NCT6793 fan controller not found" >&2
  exit 1
fi

pwm="$hwmon/pwm2"
enable="$hwmon/pwm2_enable"
rpm="$hwmon/fan2_input"

full_speed() {
  printf '1\n' > "$enable" 2>/dev/null || true
  printf '255\n' > "$pwm" 2>/dev/null || true
}
trap full_speed EXIT
trap 'exit 0' INT TERM
full_speed
sleep 3

last_level=-1
last_pwm=-1
while true; do
  rows="$(timeout 7s ssh -o BatchMode=yes -o ConnectTimeout=2 \
    -o ConnectionAttempts=1 "$M40_VM_SSH_TARGET" \
    'nvidia-smi --query-gpu=name,temperature.gpu --format=csv,noheader,nounits' \
    2>/dev/null)" || rows=""
  temp="$(printf '%s\n' "$rows" | awk -F, '$1 ~ /Tesla M40/ {
    gsub(/[[:space:]]/, "", $2); print $2; exit
  }')"

  if [[ "$temp" =~ ^[0-9]{1,2}$ ]] && (( temp <= 95 )); then
    if (( temp >= 68 )); then level=4
    elif (( temp >= 60 )); then level=3
    elif (( temp >= 50 )); then level=2
    elif (( temp >= 40 )); then level=1
    else level=0
    fi

    if (( last_level == 4 && level < 4 && temp >= 64 )); then level=4
    elif (( last_level == 3 && level < 3 && temp >= 57 )); then level=3
    elif (( last_level == 2 && level < 2 && temp >= 47 )); then level=2
    elif (( last_level == 1 && level < 1 && temp >= 37 )); then level=1
    fi

    case "$level" in
      0) next_pwm=153 ;;
      1) next_pwm=179 ;;
      2) next_pwm=204 ;;
      3) next_pwm=230 ;;
      4) next_pwm=255 ;;
    esac
    status="M40 ${temp}C"
    last_level=$level
  else
    # SSH loss is not proof that the GPU is off. Stay at full speed.
    next_pwm=255
    status="M40 temperature unavailable; full-speed failsafe"
    last_level=-1
  fi

  printf '1\n' > "$enable"
  printf '%s\n' "$next_pwm" > "$pwm"
  if (( next_pwm != last_pwm )); then
    sleep 2
    fan_rpm="$(cat "$rpm" 2>/dev/null || true)"
    echo "$status | pwm=$next_pwm | fan=${fan_rpm:-?} RPM"
    last_pwm=$next_pwm
  fi
  sleep 3
done
