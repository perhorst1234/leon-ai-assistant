import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "leon-server-preflight"
LOADER = importlib.machinery.SourceFileLoader("server_preflight", str(SCRIPT))
SPEC = importlib.util.spec_from_loader("server_preflight", LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_json_output_is_stable_and_read_only(tmp_path, capsys):
    assert MODULE.main(["--repo", str(tmp_path), "--json"]) == 0
    first = capsys.readouterr().out
    assert MODULE.main(["--repo", str(tmp_path), "--json"]) == 0
    second = capsys.readouterr().out
    payload = json.loads(first)
    second_payload = json.loads(second)
    assert payload["schema_version"] == 1
    assert payload["read_only"] is True
    assert payload.keys() == second_payload.keys()
    assert set(payload) == {"commands", "disks", "gpu", "host", "read_only", "repo", "schema_version", "systemd"}


def test_redaction_removes_identity_and_secret_values():
    value = MODULE._redact("hostname=my-box serial: ABC123 /home/alice/leon token=secret")
    assert "my-box" not in value
    assert "ABC123" not in value
    assert "alice" not in value
    assert "secret" not in value
    assert MODULE.REDACTED in value


def test_human_mode_states_read_only(tmp_path, capsys):
    assert MODULE.main(["--repo", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "read-only" in output
    assert "No installs, mounts, service changes, or writes performed." in output


def test_disk_parser_handles_spaces_and_keeps_first_lsblk_device(monkeypatch):
    def fake_run(command, _timeout):
        if command[0] == "df":
            return {"ok": True, "stdout": "Filesystem 1024-blocks Used Available Capacity Mounted on\n/Applications/HA Menu.app 100 20 80 20% /path with spaces"}
        return {"ok": True, "stdout": 'NAME="sda" SIZE="500G" TYPE="disk" FSTYPE="" MOUNTPOINT="" MODEL="SSD"'}

    monkeypatch.setattr(MODULE, "_run", fake_run)
    disks = MODULE._disks(1.0)
    assert disks["filesystems"][0]["filesystem"] == "/Applications/HA Menu.app"
    assert disks["filesystems"][0]["mountpoint"] == "/path with spaces"
    assert disks["block_devices"][0]["name"] == "sda"


def test_timeout_and_command_output_are_bounded():
    assert MODULE._timeout("30") == 30
    for value in ("inf", "nan", "31", "0"):
        try:
            MODULE._timeout(value)
        except Exception:
            pass
        else:
            raise AssertionError(f"timeout accepted: {value}")
    result = MODULE._run([sys.executable, "-c", "print('x' * 200000)"], 2.0)
    assert result["ok"] is False
    assert result["error"] == "OutputLimitExceeded"
    assert len(result["stdout"].encode()) <= MODULE.MAX_COMMAND_OUTPUT
