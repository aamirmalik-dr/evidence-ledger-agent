# v2 pre-registration: evidence-ledger-agent

Written and frozen on 2026-11-09 before any v2 question or document exists.

## Fixes (each justified by the v1 live pilot)

1. Reply parser (agentcore 0.1.2, already committed after the v1 pilot, commit 12a5a74). Evidence: 22 agent steps in the v1 pilot (16 agent, 6 ablation) were rejected as malformed; every one was a complete JSON action followed by an extra closing brace, and two episodes used up their token budget repeating it. The parser now decodes the first complete JSON object and ignores trailing text.

No other change. Prompts (ledger-prompts-v2), tools, caps, rubric and scoring code stay exactly as at v1 HEAD 45f6ff8.

## Fresh held-out family

`heldout_v2`: 12 new fictional documents on a topic the v1 families do not cover, and 10 new questions with gold labels. It has the same trap types as v1: a condition-dependent conflict, a unit trap, a correction that supersedes, a confident unsupported mechanism, an unanswerable question, and a document with an embedded instruction. It is written after this file is frozen, and it is never shown to any prompt before the live runs.

## Metrics (frozen, identical to v1)

Verdict accuracy, citation validity, support precision and recall, contradiction recall, correct abstention, unsupported claims, failures, tool calls, model calls, tokens and provider USD. All are reported with denominators, plus min and max over runs.

## Runs

- A: `openai/gpt-4.1-mini`, arms lexical, single_call, agent, agent_no_expand, 10 questions x 2 runs, max_usd 0.50.
- B: `anthropic/claude-sonnet-4.6` (3.00 / 15.00 USD per Mtok), arms agent and single_call (the strongest v1 baseline, 18/20), plus lexical (free), 1 run, max_usd 1.00.

No change of any kind after seeing v2 results.

## Addendum (2026-11-09, during run B, before any re-run)

The first attempt at run B hit HTTP 429 rate limits from OpenRouter while several sessions called the same model. 9 of its 20 episodes stopped with `adapter_error` before any model reply, after the default two short retries. That attempt is kept unchanged under `reports/aborted/live_v2_sonnet_http429/` and is not reported as a model result.

The only change is infrastructure: the adapter retry count and backoff become configurable, and run B uses 6 retries with a 5-second base backoff. Run B is then repeated once on the same frozen questions. The task, prompt, model, arms and metrics are unchanged, and no v2 outcome informs any change.

Spend on the aborted attempt: 0.248 USD. The re-run cap is 0.85 USD, so run B totals at most 1.10 USD.
