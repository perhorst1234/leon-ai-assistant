"""Regression for inspecting output before asynchronous tee collectors finish."""
import os
from pathlib import Path
import shutil

from test_control_plane import run_resume_watch


def test_resume_watch_waits_for_delayed_output_collectors(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    tee = bin_dir / "tee"
    # Deliberately delay collection, not command execution. The wrapper must join
    # collectors, rather than depend on how quickly tee is scheduled by the OS.
    tee.write_text(f'#!/usr/bin/env bash\nsleep 0.2\nexec "{shutil.which("tee")}" "$@"\n', encoding="utf-8")
    tee.chmod(0o700)
    attempts = tmp_path / "attempts"
    result = run_resume_watch(tmp_path, f'''#!/usr/bin/env bash
if [ ! -f "{attempts}" ]; then
  touch "{attempts}"
  echo "429 rate limit" >&2
  echo "Retry-After: 0"
  exit 1
fi
echo "completed"
''', extra_env={"PATH": f"{bin_dir}:{os.environ['PATH']}"})
    assert result.returncode == 0
    assert "detected likely" in result.stderr
    assert "429 rate limit" in result.stderr
    assert "completed" in result.stdout
