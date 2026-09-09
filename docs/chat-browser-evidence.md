# Connected chat browser evidence

Environment: `tests/ui_model_fixture.py` on `127.0.0.1:18765`, synthetic transport only; Gaia dev server on `localhost:13000` with the fixture token.

Observed in one focused browser run:

- Connected Chat opened from Vandaag; one composer textarea was present and the demo composer was absent.
- The fixture token connected and showed `Verbonden met Leon`.
- A new conversation was created and the preview showed the exact edited prompt, prior-message count, revision, reservation, and “Er is nog niets naar een model verstuurd.”
- Editing the prompt removed the old preview, so the stale preview could not be approved.
- After the polling fix, the active preview survived more than one 3.5-second refresh interval and remained approvable.
- Approval queued the request and produced the synthetic answer. Reloading and reconnecting restored the same conversation and answer.
- A second preview included the earlier user message and synthetic assistant answer in its displayed conversation context; approving it produced the second synthetic answer.
