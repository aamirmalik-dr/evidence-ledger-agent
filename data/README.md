# data/

Nothing needs to be downloaded. The corpus this project runs on is a small, original, fictional sample committed under `tests/fixtures/corpus/` (24 documents in two families), with questions in `tests/fixtures/` and gold labels in `evaluator/`. Every document is marked `FICTIONAL EXAMPLE DOCUMENT.` in its first line, and none is a real publication.

This folder is gitignored apart from this file. It is the place to put a private corpus for local experiments. A corpus folder needs a `manifest.json` in the format of `tests/fixtures/corpus/dev/manifest.json`; run `python scripts/freeze_corpus.py <folder>` to record the hashes. Any external material must be recorded in `docs/data_manifest.md` with its source and license before use.
