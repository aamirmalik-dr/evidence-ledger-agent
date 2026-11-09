# Evidence

Generated from saved run outputs by `python -m evidence_ledger_agent report`. Do not edit by hand.

## Mode: fixture

Fixture mode replays hand-written scripted replies for the single_call, agent and agent_no_expand arms, including deliberately planted failures. Those rows validate the loop, policy and scorer; they are not measurements of any model. The lexical arm uses no model, so its fixture rows are genuine measurements of that baseline on this corpus.

- Commit: `12a5a74f01472dced2d95c7db30f432ee98f1a25` (working tree dirty: False)
- Model: none (scripted fixture adapter)
- Prompt: ledger-prompts-v2, sha256 `702e8f169533fdf0`
- Config sha256: `3c8f29c3b833765b`
- Run: 2026-11-09T12:06:18+09:00 to 2026-11-09T12:06:41+09:00
- Hardware: Windows-10-10.0.26300-SP0, Python 3.11.9
- Episodes scored: 64
- Tokens: None, USD at listed prices: None, USD reported by provider: None, adapter retries: None

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

## Mode: live

v1 pilot on the held-out family, agentcore 0.1.1 (strict reply parser).

- Commit: `9d07e389503a789e5985ea98a6426439e908e24d` (working tree dirty: False)
- Model: openai/gpt-4.1-mini
- Prompt: ledger-prompts-v2, sha256 `8df09e930c93887d`
- Config sha256: `ec65290df76a3c88`
- Run: 2026-11-09T11:50:33+09:00 to 2026-11-09T12:02:08+09:00
- Hardware: Windows-10-10.0.26300-SP0, Python 3.11.9
- Episodes scored: 80
- Tokens: {'completion': 44890, 'prompt': 755603}, USD at listed prices: 0.3740652, USD reported by provider: 0.272652, adapter retries: 0

### Fixture hashes

- heldout/corpus: `182dadc4e2f0afdb`
- heldout/gold: `952fcc627e733d20`
- heldout/questions: `61512056af330bc9`

### Every failed, wrong or repaired episode

| Family | Arm | Task | Run | Outcome | Stop reason | Correct | Rejected finishes | Malformed | Re-prompts | Invalid citations |
|---|---|---|---|---|---|---|---|---|---|---|
| heldout | agent | ho-q01 | 0 | supported | finished | 1 | 0 | 1 | 1 | 0 |
| heldout | lexical | ho-q02 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | single_call | ho-q02 | 0 | supported | finished | 0 | 0 | 0 | 0 | 0 |
| heldout | agent | ho-q02 | 0 | abstained | abstained | 0 | 0 | 0 | 0 | 0 |
| heldout | agent_no_expand | ho-q02 | 0 | failed | max_tool_calls | 0 | 1 | 0 | 0 | 1 |
| heldout | lexical | ho-q03 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | agent | ho-q04 | 0 | supported | finished | 1 | 0 | 2 | 2 | 0 |
| heldout | lexical | ho-q05 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | agent_no_expand | ho-q05 | 0 | failed | max_tool_calls | 0 | 2 | 0 | 0 | 2 |
| heldout | agent | ho-q06 | 0 | failed | max_tokens | 0 | 0 | 5 | 5 | 0 |
| heldout | agent_no_expand | ho-q06 | 0 | supported | finished | 1 | 0 | 2 | 2 | 0 |
| heldout | lexical | ho-q07 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | lexical | ho-q08 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | single_call | ho-q08 | 0 | insufficient | finished | 1 | 0 | 0 | 0 | 1 |
| heldout | agent_no_expand | ho-q08 | 0 | failed | max_tool_calls | 0 | 0 | 0 | 0 | 0 |
| heldout | lexical | ho-q09 | 0 | insufficient | None | 0 | 0 | 0 | 0 | 0 |
| heldout | agent | ho-q09 | 0 | abstained | abstained | 0 | 0 | 0 | 0 | 0 |
| heldout | agent | ho-q10 | 0 | supported | finished | 1 | 1 | 0 | 0 | 1 |
| heldout | agent_no_expand | ho-q10 | 0 | supported | finished | 1 | 1 | 0 | 0 | 1 |
| heldout | agent_no_expand | ho-q01 | 1 | supported | finished | 1 | 2 | 0 | 0 | 2 |
| heldout | lexical | ho-q02 | 1 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | single_call | ho-q02 | 1 | supported | finished | 0 | 0 | 0 | 0 | 0 |
| heldout | agent | ho-q02 | 1 | supported | finished | 0 | 1 | 0 | 0 | 1 |
| heldout | agent_no_expand | ho-q02 | 1 | insufficient | finished | 0 | 0 | 0 | 0 | 0 |
| heldout | lexical | ho-q03 | 1 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | agent | ho-q04 | 1 | abstained | abstained | 0 | 0 | 0 | 0 | 0 |
| heldout | agent_no_expand | ho-q04 | 1 | supported | finished | 1 | 1 | 2 | 2 | 1 |
| heldout | lexical | ho-q05 | 1 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | agent | ho-q05 | 1 | failed | max_tool_calls | 0 | 0 | 1 | 1 | 0 |
| heldout | agent_no_expand | ho-q05 | 1 | failed | max_tool_calls | 0 | 1 | 1 | 1 | 2 |
| heldout | agent | ho-q06 | 1 | failed | max_tokens | 0 | 0 | 5 | 5 | 0 |
| heldout | agent_no_expand | ho-q06 | 1 | supported | finished | 1 | 1 | 0 | 0 | 1 |
| heldout | lexical | ho-q07 | 1 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | lexical | ho-q08 | 1 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout | single_call | ho-q08 | 1 | insufficient | finished | 1 | 0 | 0 | 0 | 1 |
| heldout | lexical | ho-q09 | 1 | insufficient | None | 0 | 0 | 0 | 0 | 0 |
| heldout | agent_no_expand | ho-q09 | 1 | supported | finished | 1 | 1 | 1 | 1 | 1 |
| heldout | agent | ho-q10 | 1 | supported | finished | 1 | 0 | 2 | 2 | 0 |
| heldout | agent_no_expand | ho-q10 | 1 | supported | finished | 1 | 1 | 0 | 0 | 1 |

## Mode: live_v2

v2 round on the fresh heldout_v2 family, agentcore 0.1.2 (parser accepts trailing text after a complete JSON reply). Same model, prompts and caps as v1.

- Commit: `cacaf36573708f83666db49a050303816593e09d` (working tree dirty: False)
- Model: openai/gpt-4.1-mini
- Prompt: ledger-prompts-v2, sha256 `8df09e930c93887d`
- Config sha256: `38c2d16de0051570`
- Run: 2026-11-09T14:15:25+09:00 to 2026-11-09T14:24:56+09:00
- Hardware: Windows-10-10.0.26300-SP0, Python 3.11.9
- Episodes scored: 80
- Tokens: {'completion': 32425, 'prompt': 520661}, USD at listed prices: 0.2601444, USD reported by provider: 0.195135, adapter retries: 0

### Fixture hashes

- heldout_v2/corpus: `2f12acdeb33e7c3a`
- heldout_v2/gold: `4e6cc8afc5af2b1e`
- heldout_v2/questions: `bd4b23a32cfa4866`

### Every failed, wrong or repaired episode

| Family | Arm | Task | Run | Outcome | Stop reason | Correct | Rejected finishes | Malformed | Re-prompts | Invalid citations |
|---|---|---|---|---|---|---|---|---|---|---|
| heldout_v2 | lexical | h2-q02 | 0 | insufficient | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | single_call | h2-q02 | 0 | supported | finished | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | agent | h2-q02 | 0 | supported | finished | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | agent_no_expand | h2-q02 | 0 | supported | finished | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | lexical | h2-q03 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | lexical | h2-q04 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | single_call | h2-q04 | 0 | conflicted | finished | 1 | 0 | 0 | 0 | 1 |
| heldout_v2 | agent | h2-q04 | 0 | failed | max_tool_calls | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | agent_no_expand | h2-q04 | 0 | failed | max_tool_calls | 0 | 2 | 0 | 0 | 3 |
| heldout_v2 | agent_no_expand | h2-q05 | 0 | supported | finished | 1 | 1 | 0 | 0 | 1 |
| heldout_v2 | agent | h2-q06 | 0 | supported | finished | 1 | 1 | 0 | 0 | 1 |
| heldout_v2 | agent_no_expand | h2-q06 | 0 | supported | finished | 1 | 2 | 0 | 0 | 2 |
| heldout_v2 | lexical | h2-q08 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | lexical | h2-q09 | 0 | insufficient | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | lexical | h2-q02 | 1 | insufficient | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | single_call | h2-q02 | 1 | supported | finished | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | agent | h2-q02 | 1 | supported | finished | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | agent_no_expand | h2-q02 | 1 | supported | finished | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | lexical | h2-q03 | 1 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | lexical | h2-q04 | 1 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | single_call | h2-q04 | 1 | conflicted | finished | 1 | 0 | 0 | 0 | 1 |
| heldout_v2 | agent | h2-q04 | 1 | failed | max_tool_calls | 0 | 3 | 0 | 0 | 3 |
| heldout_v2 | agent_no_expand | h2-q04 | 1 | failed | max_tool_calls | 0 | 2 | 0 | 0 | 3 |
| heldout_v2 | agent_no_expand | h2-q05 | 1 | supported | finished | 1 | 1 | 0 | 0 | 1 |
| heldout_v2 | agent | h2-q06 | 1 | supported | finished | 1 | 1 | 0 | 0 | 1 |
| heldout_v2 | agent_no_expand | h2-q06 | 1 | supported | finished | 1 | 1 | 0 | 0 | 1 |
| heldout_v2 | lexical | h2-q08 | 1 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | agent_no_expand | h2-q08 | 1 | failed | max_tool_calls | 0 | 1 | 0 | 0 | 1 |
| heldout_v2 | lexical | h2-q09 | 1 | insufficient | None | 0 | 0 | 0 | 0 | 0 |

## Mode: live_v2_sonnet

v2 round, second model on the same heldout_v2 questions: the agent arm, the strongest v1 baseline (single call) and the lexical baseline, one run.

- Commit: `0ad47e2ffdd2f3701ac0501baeff53a947ca9a8c` (working tree dirty: False)
- Model: anthropic/claude-sonnet-4.6
- Prompt: ledger-prompts-v2, sha256 `adeba45786ceecae`
- Config sha256: `c80334faf3a188d2`
- Run: 2026-11-09T14:25:50+09:00 to 2026-11-09T14:31:14+09:00
- Hardware: Windows-10-10.0.26300-SP0, Python 3.11.9
- Episodes scored: 30
- Tokens: {'completion': 7330, 'prompt': 110360}, USD at listed prices: 0.44103, USD reported by provider: 0.44103, adapter retries: 14

### Fixture hashes

- heldout_v2/corpus: `2f12acdeb33e7c3a`
- heldout_v2/gold: `4e6cc8afc5af2b1e`
- heldout_v2/questions: `bd4b23a32cfa4866`

### Every failed, wrong or repaired episode

| Family | Arm | Task | Run | Outcome | Stop reason | Correct | Rejected finishes | Malformed | Re-prompts | Invalid citations |
|---|---|---|---|---|---|---|---|---|---|---|
| heldout_v2 | lexical | h2-q02 | 0 | insufficient | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | agent | h2-q02 | 0 | supported | finished | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | lexical | h2-q03 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | lexical | h2-q04 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | lexical | h2-q08 | 0 | supported | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | lexical | h2-q09 | 0 | insufficient | None | 0 | 0 | 0 | 0 | 0 |
| heldout_v2 | agent | h2-q09 | 0 | supported | finished | 1 | 0 | 0 | 1 | 0 |

## Measured results (no-model baseline and live model)

| Mode | Family | Arm | Verdict accuracy | Citation validity | Support precision | Support recall | Contradiction recall | Correct abstention | Unsupported claims | Failures | Accuracy per run (min to max) | Tool calls | Model calls | Tokens | USD (provider) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no model, deterministic | dev | lexical | 0.50 (3/6) | 1.00 (5/5) | 0.40 (2/5) | 0.33 (2/6) | 0.00 (0/1) | 0.50 (1/2) | 3 | 0 | single deterministic run | 0 | 0 | 0 | 0 |
| no model, deterministic | heldout | lexical | 0.40 (4/10) | 1.00 (9/9) | 0.33 (3/9) | 0.27 (3/11) | 0.00 (0/2) | 0.00 (0/3) | 6 | 0 | single deterministic run | 0 | 0 | 0 | 0 |
| live v1, gpt-4.1-mini | heldout | lexical | 0.40 (8/20) | 1.00 (18/18) | 0.33 (6/18) | 0.27 (6/22) | 0.00 (0/4) | 0.00 (0/6) | 12 | 0 | 0.40 to 0.40 (2 runs) | 0 | 0 | 0 | 0 |
| live v1, gpt-4.1-mini | heldout | single_call | 0.90 (18/20) | 0.92 (23/25) | 0.91 (21/23) | 0.73 (16/22) | 0.50 (2/4) | 1.00 (6/6) | 2 | 0 | 0.90 to 0.90 (2 runs) | 0 | 20 | 30343 | 0.0137 |
| live v1, gpt-4.1-mini | heldout | agent | 0.65 (13/20) | 0.83 (10/12) | 0.89 (8/9) | 0.36 (8/22) | 0.25 (1/4) | 1.00 (6/6) | 1 | 3 | 0.60 to 0.70 (2 runs) | 112 | 144 | 400940 | 0.1273 |
| live v1, gpt-4.1-mini | heldout | agent_no_expand | 0.75 (15/20) | 0.60 (18/30) | 0.79 (11/14) | 0.50 (11/22) | 0.00 (0/4) | 0.83 (5/6) | 0 | 4 | 0.70 to 0.80 (2 runs) | 136 | 148 | 369210 | 0.1316 |
| live v2, gpt-4.1-mini | heldout_v2 | lexical | 0.50 (10/20) | 1.00 (14/14) | 0.14 (2/14) | 0.09 (2/22) | 0.00 (0/4) | 0.33 (2/6) | 12 | 0 | 0.50 to 0.50 (2 runs) | 0 | 0 | 0 | 0 |
| live v2, gpt-4.1-mini | heldout_v2 | single_call | 0.90 (18/20) | 0.92 (22/24) | 0.91 (20/22) | 0.73 (16/22) | 0.00 (0/4) | 1.00 (6/6) | 2 | 0 | 0.90 to 0.90 (2 runs) | 0 | 20 | 22921 | 0.0135 |
| live v2, gpt-4.1-mini | heldout_v2 | agent | 0.80 (16/20) | 0.83 (24/29) | 0.67 (14/21) | 0.55 (12/22) | 0.00 (0/4) | 1.00 (6/6) | 2 | 2 | 0.80 to 0.80 (2 runs) | 99 | 99 | 253450 | 0.0829 |
| live v2, gpt-4.1-mini | heldout_v2 | agent_no_expand | 0.75 (15/20) | 0.67 (24/36) | 0.59 (13/22) | 0.55 (12/22) | 0.00 (0/4) | 0.83 (5/6) | 2 | 3 | 0.70 to 0.80 (2 runs) | 112 | 112 | 276715 | 0.0987 |
| live v2, claude-sonnet-4.6 | heldout_v2 | lexical | 0.50 (5/10) | 1.00 (7/7) | 0.14 (1/7) | 0.09 (1/11) | 0.00 (0/2) | 0.33 (1/3) | 6 | 0 | 0.50 to 0.50 (1 run) | 0 | 0 | 0 | 0 |
| live v2, claude-sonnet-4.6 | heldout_v2 | single_call | 1.00 (10/10) | 1.00 (13/13) | 1.00 (13/13) | 1.00 (11/11) | 1.00 (2/2) | 1.00 (3/3) | 0 | 0 | 1.00 to 1.00 (1 run) | 0 | 10 | 12959 | 0.0652 |
| live v2, claude-sonnet-4.6 | heldout_v2 | agent | 0.90 (9/10) | 1.00 (11/11) | 0.91 (10/11) | 0.82 (9/11) | 0.50 (1/2) | 1.00 (3/3) | 1 | 0 | 0.90 to 0.90 (1 run) | 36 | 37 | 104731 | 0.3758 |

## Scorer checks (scripted replies, not model results)

| Mode | Family | Arm | Verdict accuracy | Citation validity | Support precision | Support recall | Contradiction recall | Correct abstention | Unsupported claims | Failures | Rejected finishes | Tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fixture, scripted | dev | single_call | 1.00 (6/6) | 0.83 (5/6) | 1.00 (5/5) | 0.83 (5/6) | 1.00 (1/1) | 1.00 (2/2) | 1 | 0 | 0 | 0 |
| fixture, scripted | dev | agent | 0.83 (5/6) | 0.86 (6/7) | 0.83 (5/6) | 0.83 (5/6) | 1.00 (1/1) | 0.50 (1/2) | 1 | 0 | 1 | 25 |
| fixture, scripted | dev | agent_no_expand | 0.83 (5/6) | 0.86 (6/7) | 0.83 (5/6) | 0.83 (5/6) | 1.00 (1/1) | 0.50 (1/2) | 1 | 0 | 1 | 25 |
| fixture, scripted | heldout | single_call | 0.90 (9/10) | 1.00 (10/10) | 0.90 (9/10) | 0.82 (9/11) | 0.50 (1/2) | 1.00 (3/3) | 1 | 0 | 0 | 0 |
| fixture, scripted | heldout | agent | 0.90 (9/10) | 1.00 (10/10) | 1.00 (10/10) | 0.82 (9/11) | 0.50 (1/2) | 1.00 (3/3) | 0 | 1 | 0 | 40 |
| fixture, scripted | heldout | agent_no_expand | 0.90 (9/10) | 1.00 (10/10) | 1.00 (10/10) | 0.82 (9/11) | 0.50 (1/2) | 1.00 (3/3) | 0 | 1 | 0 | 40 |

## Limitations

- The corpus is small (24 fictional documents, 16 questions) and written by the author; it is a test bed, not a benchmark.
- Citation checks prove quote identity and provenance, not scientific support; support is scored against hand-written gold spans with a 50 percent overlap rule.
- Condition recall is a substring check over the answer's conditions, claim and rationale.
- Fixture results for model arms are scripted and carry no information about model quality.
- Each live run covers 10 held-out questions at temperature 0 (two runs per arm for gpt-4.1-mini, one for the second model): exploratory samples, not a ranking. Run-to-run spread is shown as min and max.

## Reproduce

- fixture: `python -m evidence_ledger_agent evaluate --config configs/fixture.yaml && python -m evidence_ledger_agent report --update-readme`
- live: `git checkout 9d07e38 && python -m evidence_ledger_agent evaluate --config configs/live.yaml --require-live`
- live_v2: `python -m evidence_ledger_agent evaluate --config configs/live_v2_mini.yaml --require-live`
- live_v2_sonnet: `python -m evidence_ledger_agent evaluate --config configs/live_v2_sonnet.yaml --require-live && python -m evidence_ledger_agent report --update-readme`
- audit: `python -m evidence_ledger_agent verify`
