# Error Log

Every real error hit during development, its cause, and the fix.

| Date | Where | Error | Cause | Fix |
|------|-------|-------|-------|-----|
| 2026-06-01 | gemma.py / live demo | Gemma fallback always returned "could not verify"; `ollama list` showed no `gemma3` model | `GemmaClient` defaulted to `model="gemma3:4b"`, but this machine has `gemma4:latest` (9.6 GB) and `gemma4:31b-cloud` installed instead. The HTTP call to Ollama failed (model not found) and was swallowed by the `except Exception: return None` graceful-degradation path. | Changed the default `model` to `gemma4:latest` to match the installed model. Verified live: classifying an unknown ingredient ("polysorbate 80") now returns a `source=gemma` result. To use a different model, pass `GemmaClient(model="...")`. |
