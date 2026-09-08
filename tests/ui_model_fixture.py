"""Manual browser fixture only. Never uses a real key, provider or existing DB.

Run with PYTHONPATH=src python3 tests/ui_model_fixture.py; CTRL-C cleans up.
Use dashboard token 'leon-local-ui-fixture' ONLY against this isolated fixture.
"""
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import tempfile
import threading
import time

from leon_control_plane import server
from leon_control_plane.local_worker import LocalWorker
from leon_control_plane.model_work import ModelExecutor
from leon_control_plane.openai_text import MODEL, OpenAIConfig
from leon_control_plane.store import ControlPlaneStore
from leon_control_plane.work_queue import WorkQueue


def main():
    with tempfile.TemporaryDirectory(prefix="leon-ui-model-") as directory:
        root = Path(directory)
        server.ENV_PATH = root / "unused.env"
        server.STORE = ControlPlaneStore(root / "control.sqlite", Path(__file__).resolve().parents[1] / "state/control-plane.seed.json")
        os.environ["LEON_DASHBOARD_TOKEN"] = "leon-local-ui-fixture"
        os.environ["LEON_DASHBOARD_AUTH_MODE"] = "required"
        queue = WorkQueue(server.STORE)
        server.STORE.create_task(title="Browserproef — nepmodel", goal="Test UI approval only", risk_level="low")
        def fake_transport(payload, key):
            time.sleep(1)
            return {"model": MODEL, "status": "completed", "error": None,
                    "usage": {"input_tokens": 24, "output_tokens": 12}, "output": [
                        {"type": "message", "role": "assistant", "content": [{"type": "output_text",
                         "text": "Dit is een lokaal testantwoord. Er is geen OpenAI-aanroep gedaan."}]}]}
        worker = LocalWorker(queue, model_executor=ModelExecutor(queue,
                             config=OpenAIConfig(True, "synthetic-only", 100000, 100000), transport=fake_transport))
        stopped = threading.Event()
        def work():
            while not stopped.is_set():
                worker.run_once()
                stopped.wait(.2)
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        try:
            with ThreadingHTTPServer(("127.0.0.1", 18765), server.Handler) as http:
                print("Fixture ready: 127.0.0.1:18765, temporary SQLite, synthetic transport only", flush=True)
                http.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            stopped.set()
            thread.join(5)


if __name__ == "__main__":
    main()
