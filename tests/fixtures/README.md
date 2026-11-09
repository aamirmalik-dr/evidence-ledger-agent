# Test fixtures

Everything in this folder is original, synthetic and fictional. No document here is a real publication, and every material name (LX-4, CM-2, RT-1, GZ-9, SX-2, TQ-5, AL-3, PB-1) is invented.

## Corpus

| Folder | Documents | Topic | Role |
|---|---|---|---|
| `corpus/dev/` | 12 | oxygen-evolution catalysts | development family, 6 questions |
| `corpus/heldout/` | 12 | solid-state battery materials | held-out family, 10 questions, frozen 2026-11-09 before any prompt work |

Each document starts with a `FICTIONAL EXAMPLE DOCUMENT.` line, and `manifest.json` records its title, kind, date, conditions, the document it supersedes (if any) and the SHA-256 of its normalized text. Loading the corpus fails if any document no longer matches its hash. After editing a document, run `python scripts/freeze_corpus.py`.

Built-in traps, per family:

| Trap | Development | Held-out |
|---|---|---|
| Apparent conflict explained by a condition | LX-4 stable at pH 14, unstable at pH 7 | GZ-9 above 5 mS cm-1 only at 80 °C |
| Genuine conflict under the same conditions | none | TQ-5 original report vs failed replication |
| Unit that changes the reading | 0.62 A cm-2 vs a 500 mA cm-2 threshold | 0.035 kΩ cm2 vs 50 Ω cm2; 6.5 × 10-3 S cm-1 |
| Superseding document | correction notice for RT-1 | withdrawal of the AL-3 preprint |
| Confident claim without data | LX-4 lattice-oxygen perspective | GZ-9 dendrite opinion piece |
| Unanswerable question | CM-2 in acid | GZ-9 beyond 1000 cycles (only 200 reported) |
| Embedded instruction in document text | dev-09 asks for the API key | ho-10 asks to approve everything and print credentials |

Gold labels live in `evaluator/`, outside the package and outside this folder.

## Scripted model replies (`scripts/`)

Fixture mode replays these replies instead of calling a model. They are generated from compact hand-written plans by `scripts/make_fixture_scripts.py`. They exercise the loop, the policy and the scorer. They are not model outputs, and fixture results for the `single_call`, `agent` and `agent_no_expand` arms say nothing about how well any model performs.

Planted failure cases, chosen to exercise specific code paths:

| Arm | Task | Planted behaviour | Path exercised |
|---|---|---|---|
| agent | dev-q2 | first finish quotes "620 mA cm-2", which the document never says | policy rejects the finish, agent retries |
| agent | dev-q4 | final verdict "supported" from a perspective without data | wrong verdict, unsupported-claim count |
| agent | dev-q5 | first reply is prose, not JSON | corrective re-prompt |
| agent | ho-q05 | keeps searching and never finishes | tool-call cap, failed episode |
| single_call | dev-q2 | the only citation paraphrases the source | citation validity, unsupported claim |
| single_call | ho-q02 | answers "supported" from the 80 °C value only | wrong verdict, missed contradiction |

The `agent_no_expand` scripts are derived mechanically from the `agent` scripts by replacing each `expand_context` call with an equivalent `read_span` call, so in fixture mode the ablation only verifies that the tool is removed from the allowlist and the prompt. Measuring what the ablation costs needs a live model.
