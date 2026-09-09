# Delivery acceptance

Validated locally on macOS on 9 September 2026 with an isolated private runtime,
fresh SQLite database, generated dashboard token, and no live model or API key.

Command:

```sh
./scripts/leon-delivery-smoke --backend-port 18875 --web-port 13011 \
  --evidence data/verification/delivery-smoke.txt
```

The smoke check deliberately quotes the generated dotenv token, reads it with
Leon's literal parser, then completes the real setup, start, authenticated Python
API and web proxy requests, doctor, online SQLite backup, stop, and restore flow.
Both authenticated requests returned HTTP 200. Doctor saw backend, worker, and
web services. The backup passed SQLite integrity checking, restore preserved a
marker written while services were online, and all three owned process groups
exited after stop.

Focused regression result: `PYTHONPATH=src .venv/bin/pytest -q
tests/test_delivery.py` passed 6 tests. The reusable smoke check also prevents
port reuse, starts the backend before the worker touches a fresh database, and
requires Vite to bind the requested port. This is local delivery evidence; Ubuntu
target-hardware acceptance remains separate.
