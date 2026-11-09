# Evidence

Generated from saved run outputs by `python -m evidence_ledger_agent report`. Do not edit by hand.

## Fixture mode

Fixture mode replays hand-written scripted replies for the single_call, agent and agent_no_expand arms, including deliberately planted failures. Those rows validate the loop, policy and scorer; they are not measurements of any model. The lexical arm uses no model, so its fixture rows are genuine measurements of that baseline on this corpus.

- Commit: `aa2d2950a0d053419b724e2defe755acb723cc9a` (working tree dirty: False)
- Model: none (scripted fixture adapter)
- Prompt: ledger-prompts-v1, sha256 `fc7d2e3c607462af`
- Config sha256: `3c8f29c3b833765b`
- Run: 2026-11-09T11:13:28+09:00 to 2026-11-09T11:13:45+09:00
- Hardware: Windows-10-10.0.26300-SP0, Python 3.11.9
- Episodes scored: 64
- Tokens: None, USD: None

### Fixture hashes

- dev/corpus: `428081366b3b73ec`
- dev/gold: `9f6295b261f0c5ea`
- dev/questions: `e38274cb0bff26a5`
- dev/script/agent: `58c1376954500ae5`
- dev/script/agent_no_expand: `73b028e4a5c5771d`
- dev/script/single_call: `1b1d2de5e242cd96`
- heldout/corpus: `182dadc4e2f0afdb`
- heldout/gold: `952fcc627e733d20`
- heldout/questions: `61512056af330bc9`
- heldout/script/agent: `c7c36c70a7a7b2e2`
- heldout/script/agent_no_expand: `4e276a6f78b9993b`
- heldout/script/single_call: `60a774633dbbb50e`

### Every failed, wrong or repaired episode

| Family | Arm | Task | Run | Outcome | Stop reason | Correct | Rejected finishes | Malformed | Re-prompts | Invalid citations |
|---|---|---|---|---|---|---|---|---|---|---|
| dev | lexical | dev-q1 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| dev | single_call | dev-q2 | 0 | supported | finished | 1 | 0 | 0 | 0 | 1 |
| dev | agent | dev-q2 | 0 | supported | finished | 1 | 1 | 0 | 0 | 1 |
| dev | agent_no_expand | dev-q2 | 0 | supported | finished | 1 | 1 | 0 | 0 | 1 |
| dev | lexical | dev-q3 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| dev | lexical | dev-q4 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| dev | agent | dev-q4 | 0 | supported | finished | 0 | 0 | 0 | 0 | 0 |
| dev | agent_no_expand | dev-q4 | 0 | supported | finished | 0 | 0 | 0 | 0 | 0 |
| dev | agent | dev-q5 | 0 | abstained | abstained | 1 | 0 | 0 | 1 | 0 |
| dev | agent_no_expand | dev-q5 | 0 | abstained | abstained | 1 | 0 | 0 | 1 | 0 |
| heldout | lexical | ho-q02 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | single_call | ho-q02 | 0 | supported | finished | 0 | 0 | 0 | 0 | 0 |
| heldout | lexical | ho-q03 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | lexical | ho-q05 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | agent | ho-q05 | 0 | failed | max_tool_calls | 0 | 0 | 0 | 0 | 0 |
| heldout | agent_no_expand | ho-q05 | 0 | failed | max_tool_calls | 0 | 0 | 0 | 0 | 0 |
| heldout | lexical | ho-q07 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | lexical | ho-q08 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | lexical | ho-q09 | 0 | insufficient | None | 0 | 0 | 0 | 0 | 0 |

## Live mode

Pending. No saved outputs exist for this mode.

## Metrics

| Mode | Family | Arm | Verdict accuracy | Citation validity | Support precision | Support recall | Contradiction recall | Correct abstention | Unsupported claims | Failures | Tool calls | Model calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fixture, deterministic | dev | lexical | 0.50 (3/6) | 1.00 (5/5) | 0.40 (2/5) | 0.33 (2/6) | 0.00 (0/1) | 0.50 (1/2) | 3 | 0 | 0 | 0 |
| fixture, scripted | dev | single_call | 1.00 (6/6) | 0.83 (5/6) | 1.00 (5/5) | 0.83 (5/6) | 1.00 (1/1) | 1.00 (2/2) | 1 | 0 | 0 | 6 |
| fixture, scripted | dev | agent | 0.83 (5/6) | 0.86 (6/7) | 0.83 (5/6) | 0.83 (5/6) | 1.00 (1/1) | 0.50 (1/2) | 1 | 0 | 25 | 26 |
| fixture, scripted | dev | agent_no_expand | 0.83 (5/6) | 0.86 (6/7) | 0.83 (5/6) | 0.83 (5/6) | 1.00 (1/1) | 0.50 (1/2) | 1 | 0 | 25 | 26 |
| fixture, deterministic | heldout | lexical | 0.40 (4/10) | 1.00 (9/9) | 0.33 (3/9) | 0.27 (3/11) | 0.00 (0/2) | 0.00 (0/3) | 6 | 0 | 0 | 0 |
| fixture, scripted | heldout | single_call | 0.90 (9/10) | 1.00 (10/10) | 0.90 (9/10) | 0.82 (9/11) | 0.50 (1/2) | 1.00 (3/3) | 1 | 0 | 0 | 10 |
| fixture, scripted | heldout | agent | 0.90 (9/10) | 1.00 (10/10) | 1.00 (10/10) | 0.82 (9/11) | 0.50 (1/2) | 1.00 (3/3) | 0 | 1 | 40 | 40 |
| fixture, scripted | heldout | agent_no_expand | 0.90 (9/10) | 1.00 (10/10) | 1.00 (10/10) | 0.82 (9/11) | 0.50 (1/2) | 1.00 (3/3) | 0 | 1 | 40 | 40 |
| live: pending | | | | | | | | | | | | |

## Limitations

- The corpus is small (24 fictional documents, 16 questions) and written by the author; it is a test bed, not a benchmark.
- Citation checks prove quote identity and provenance, not scientific support; support is scored against hand-written gold spans with a 50 percent overlap rule.
- Condition recall is a substring check over the answer's conditions, claim and rationale.
- Fixture results for model arms are scripted and carry no information about model quality.
- No live model has been evaluated yet; live results are pending.

## Reproduce

- fixture: `python -m evidence_ledger_agent evaluate --config configs/fixture.yaml && python -m evidence_ledger_agent report --update-readme`
- live: `python -m evidence_ledger_agent evaluate --config configs/live.yaml --require-live && python -m evidence_ledger_agent report --update-readme`
- audit: `python -m evidence_ledger_agent verify`
