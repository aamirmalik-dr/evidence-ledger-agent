# evidence-ledger-agent

An LLM agent that checks narrow materials-science claims against a local document corpus and leaves an audit trail a reviewer can verify without trusting the model. The model chooses which searches to run and which spans to read, and decides when the evidence is enough. It then either commits to a verdict (`supported`, `conflicted`, `insufficient`) or abstains. Every quote in its answer is bound to a document hash and exact character offsets, and the policy layer rejects any answer that quotes text the agent never read or that does not appear verbatim in the source. The point of the project is the ledger and the refusal to over-claim, not fluent summaries. It is compared against a lexical baseline and a single-call baseline on the same corpus, using an evaluator whose labels the agent cannot reach.

The corpus is original and fictional: 24 short documents written for this project, each marked as a fictional example.

## A ledger entry, and how to check it

The pH-dependent stability question from the fixture demo produces this record (`reports/demo_ledger.json`, first citation shown):

```json
{
 "task_id": "dev-q1",
 "question": "Claim to check: catalyst LX-4 is stable for 100 hours of continuous oxygen evolution.",
 "outcome": "conflicted",
 "claim": "LX-4 is stable for 100 hours at pH 14 but deactivates within 12 hours at pH 7.",
 "conditions": {"pH": "stable at pH 14 (1 M KOH), not stable at pH 7 (phosphate buffer)"},
 "citations": [
  {
   "doc_id": "dev-01",
   "start": 665,
   "end": 738,
   "doc_hash": "69439517de63cc16252f7700b10a4dd3858a1dfa4d883ddf588b6e10f80bec70",
   "quote": "All three LX-4 electrodes remained stable for the full 100 hours at pH 14",
   "read_span_id": "dev-01:156:1217"
  }
 ]
}
```

Anyone can confirm it without running the agent:

```python
from evidence_ledger_agent.corpus import Corpus

doc = Corpus.load("tests/fixtures/corpus/dev").get("dev-01")
assert doc.sha256 == "69439517de63cc16252f7700b10a4dd3858a1dfa4d883ddf588b6e10f80bec70"
assert doc.text[665:738] == "All three LX-4 electrodes remained stable for the full 100 hours at pH 14"
```

`python -m evidence_ledger_agent verify` does the same for every citation in a saved ledger: it checks that the document exists, that its hash is unchanged, and that the quote matches the stored text at its offsets.

What the citation checks prove is provenance: the words exist, unmodified, where the ledger says, and the agent read them. Whether they support the claim is a separate question, answered by the evaluator against gold spans.

## What it does and does not do

Does:
- Runs a bounded tool loop over five typed tools: `search`, `read_span`, `expand_context`, `finish`, `abstain`. The model picks every call from earlier results.
- Rejects a `finish` that cites an unread span, an unknown document, out-of-range offsets, a quote that is not in the source (only whitespace may differ, for example a paragraph break quoted as a space; the ledger then stores the exact source text), a `supported` verdict without a citation, or a `conflicted` verdict that cites fewer than two documents. The agent sees the typed error and can try again.
- Enforces caps on steps, tool calls, tokens and wall time per episode, and on tokens and dollars per evaluation run. Hitting a cap is a recorded stop reason.
- Checkpoints atomically after every result, writing each action to the checkpoint before it runs, and resumes without repeating completed actions.
- Writes sanitized JSONL traces with the model's one-sentence summary per step, never hidden reasoning.
- Scores answers on verdict accuracy, citation validity, quote fidelity, support precision and recall, contradiction recall, correct abstention, condition recall, unsupported claims, failures and cost. Every metric is reported with its numerator and denominator.

Does not:
- Judge whether a source is scientifically correct.
- Use real literature. The corpus is a fictional test bed of 24 documents, not a benchmark.
- Give the model a shell, code execution, file access or network access.
- Show that iterating beats a single well-retrieved prompt. On this corpus it did not (see below).

## How it works

```
src/evidence_ledger_agent/
  agentcore/           reusable core, no domain knowledge (573 lines of code, version 0.1.2)
    schemas.py         typed Action, ToolResult, closed ToolError codes, StopReason, BaseAgentState
    adapters.py        adapter protocol; fixture, replay and OpenAI-compatible adapters
    policy.py          tool registry, allowlist, argument validation, budgets, idempotency
    loop.py            observe, decide, validate, execute, checkpoint; atomic checkpoint store
    trace.py           sanitized JSONL event log
  schemas.py           Document, SpanRef, VerifiedCitation, LedgerState, LedgerEntry
  corpus.py            normalized, immutable, hashed document store
  retrieval.py         BM25 with deterministic tie-breaking
  tools.py             the five tools and the finish precheck
  citation_checks.py   quote identity and provenance checks, ledger audit
  prompts.py           versioned, hashed prompts
  agent.py             one episode, state to ledger entry
  baselines.py         lexical and single-call baselines
  evaluation.py        rubric scoring, evaluation runner, comparison
  report.py            evidence.json, evidence.md, README table
evaluator/             gold labels, outside the package, never a tool input
tests/fixtures/        fictional corpus, questions, scripted fixture replies
configs/               fixture.yaml, live.yaml (frozen caps and settings)
reports/               saved outputs, traces and evidence files
docs/                  design, threat model, rubric, data manifest
```

Each step, the model sees the question, the stated conditions, which documents and spans it has seen, how much budget is left, and the last four tool results inside `<tool_result trust="untrusted-data">` blocks. It must reply with one JSON object, `{"summary": ..., "action": {"tool": ..., "arguments": {...}}}`. A malformed reply gets one corrective re-prompt; a second failure is recorded and costs a step. Gold labels are loaded only by the scorer, after the episode ends. [docs/design.md](docs/design.md) covers the loop, checkpointing and the known gap in idempotency.

`agentcore` was written here first. The later repositories in this series copy it verbatim and record any change in their own `docs/agentcore_changes.md`. Version 0.1.1 added bounded retries for transient HTTP failures, a model id pinned by the config, and the provider-reported cost of each call. Version 0.1.2 accepts trailing text after a complete JSON reply.

## Quickstart

Python 3.11. Nothing is downloaded and no model is called.

```bash
git clone https://github.com/aamirmalik-dr/evidence-ledger-agent
cd evidence-ledger-agent
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
python -m evidence_ledger_agent demo --mode fixture
```

The demo audits two development questions with the scripted fixture adapter and prints each tool call and the ledger table. In the pH question, the agent reads a narrow window of the alkaline report, expands it to reach the scope caveat, searches with a `pH: 7` filter, finds the near-neutral report, and returns `conflicted` with both citations and the pH condition. In the unanswerable question, its first reply is not valid JSON; after the corrective re-prompt it searches, reads the CM-2 report, searches again and abstains.

```bash
python -m evidence_ledger_agent evaluate --config configs/fixture.yaml   # all arms, both families
python -m evidence_ledger_agent report --update-readme                   # evidence files and the table below
python -m evidence_ledger_agent verify                                   # re-audit every saved citation
python -m pytest
```

## What was measured

The table holds only real measurements: the lexical baseline, which calls no model, and three live runs on 2026-11-09 through OpenRouter at temperature 0. The v1 pilot ran on the original held-out family with `openai/gpt-4.1-mini`. The v2 round ran on a fresh family (`heldout_v2`, 12 new fictional documents on perovskite solar cells and 10 new questions) with the same model, and with `anthropic/claude-sonnet-4.6` as a second model. Every failure, abstention, malformed reply and budget stop stays in the denominators. With 10 to 20 episodes per arm these are exploratory samples, not a ranking.

<!-- evidence-table:start -->
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
<!-- evidence-table:end -->

### v2 round

What changed between v1 and v2, and why: in v1, 22 agent steps were rejected only because the model ended valid JSON with an extra closing brace. The reply parser (agentcore 0.1.2) now reads the first complete JSON object, and nothing else changed. Prompts, tools, caps and rubric are as in v1. The new questions were written after this fix was frozen, so neither the fix nor the prompts saw them. The plan is in [docs/v2_preregistration.md](docs/v2_preregistration.md).

- The parser fix worked: malformed steps fell from 22 to 0, and the agent rose from 13 to 16 of 20 verdicts with the same model.
- The single call still wins with gpt-4.1-mini: 18 of 20, against 16 for the agent, 15 for the agent without `expand_context` and 10 for the lexical baseline. It also used about a tenth of the tokens (23 thousand against 253 thousand).
- Every arm missed both conflict questions (contradiction recall 0 of 4). The condition-dependent stability claim was called `supported` from the dry-nitrogen report alone. On the failed replication, the agents spent their 10 tool calls without finishing (2 of the agent's 4 misses).
- With the second model, one run, the ranking held: the single call got 10 of 10, with every citation valid and both conflicts found. The agent got 9 of 10, missing the condition-dependent conflict. Sonnet 4.6 cost 0.065 USD for the single call and 0.376 USD for the agent.
- Run-B note: the first attempt at the Sonnet run hit HTTP 429 rate limits while other sessions used the same model. 9 of its 20 episodes failed before any reply. That attempt is kept in `reports/aborted/` and is not counted. The run was repeated once with more adapter retries, with nothing else changed.

### v1 pilot

What the v1 pilot showed:

- The single call wins. Given the top four BM25 passages in one prompt, the same model got 18 of 20 held-out verdicts right, against 13 of 20 for the iterative agent and 15 of 20 for the agent without `expand_context`. It also cost about a tenth as much: 30 thousand tokens for 20 answers, against 370 to 400 thousand for each agent arm. On a corpus this small, top-four retrieval already holds nearly all of the evidence, so iterating mostly adds ways to fail.
- Most agent losses are protocol failures, not wrong verdicts. 16 agent steps and 6 ablation steps were rejected as malformed, and every one of them was a complete, valid JSON action followed by an extra closing brace. The corrective re-prompt did not fix it, and 2 agent episodes used up their token budget repeating the same malformed reply. The other failures (1 agent, 4 ablation episodes) hit the 10-call tool cap without finishing. agentcore 0.1.2 decodes the first complete JSON object and ignores trailing text, and it would have accepted all 22 of those replies. The pilot was not re-run on the same held-out questions; the v2 round above measures the fix on a fresh family instead.
- The agent abstained correctly on all 6 unanswerable episodes (5 of 6 without `expand_context`) and made 1 unsupported claim (0 without `expand_context`), against 2 for the single call and 12 for the lexical baseline. The agent also abstained on 3 answerable episodes; the ablation on none.
- Removing `expand_context` did not hurt verdict accuracy here (15 against 13 of 20). It did produce more rejected finishes (11 against 2) and lower citation validity (18 of 30 against 10 of 12).
- Contradiction recall is weak everywhere: 2 of 4 for the single call, 1 of 4 for the agent, 0 of 4 for the ablation and the lexical baseline.
- Cost: 755,603 prompt and 44,890 completion tokens in total. OpenRouter reported 0.273 USD for the run. At the listed prices used by the cap check it would have been 0.374 USD; the difference is provider-side prompt caching.

[reports/evidence.md](reports/evidence.md) lists every failed, wrong or repaired episode, and `reports/live/traces/` holds the sanitized trace of each one, including the raw replies.

## Scorer checks (scripted replies, not model results)

In fixture mode, the `single_call`, `agent` and `agent_no_expand` arms replay hand-written replies with planted failures, listed in [tests/fixtures/README.md](tests/fixtures/README.md). These rows only show that the policy and scorer catch what they should: a paraphrased quote lowers citation validity and counts as an unsupported claim, a fabricated quote is rejected at `finish`, a confident perspective accepted as support counts as a wrong verdict, and an episode that never finishes is a failure with stop reason `max_tool_calls`. The agent and ablation rows are identical by construction. None of these numbers describes a model.

<!-- scorer-table:start -->
| Mode | Family | Arm | Verdict accuracy | Citation validity | Support precision | Support recall | Contradiction recall | Correct abstention | Unsupported claims | Failures | Rejected finishes | Tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fixture, scripted | dev | single_call | 1.00 (6/6) | 0.83 (5/6) | 1.00 (5/5) | 0.83 (5/6) | 1.00 (1/1) | 1.00 (2/2) | 1 | 0 | 0 | 0 |
| fixture, scripted | dev | agent | 0.83 (5/6) | 0.86 (6/7) | 0.83 (5/6) | 0.83 (5/6) | 1.00 (1/1) | 0.50 (1/2) | 1 | 0 | 1 | 25 |
| fixture, scripted | dev | agent_no_expand | 0.83 (5/6) | 0.86 (6/7) | 0.83 (5/6) | 0.83 (5/6) | 1.00 (1/1) | 0.50 (1/2) | 1 | 0 | 1 | 25 |
| fixture, scripted | heldout | single_call | 0.90 (9/10) | 1.00 (10/10) | 0.90 (9/10) | 0.82 (9/11) | 0.50 (1/2) | 1.00 (3/3) | 1 | 0 | 0 | 0 |
| fixture, scripted | heldout | agent | 0.90 (9/10) | 1.00 (10/10) | 1.00 (10/10) | 0.82 (9/11) | 0.50 (1/2) | 1.00 (3/3) | 0 | 1 | 0 | 40 |
| fixture, scripted | heldout | agent_no_expand | 0.90 (9/10) | 1.00 (10/10) | 1.00 (10/10) | 0.82 (9/11) | 0.50 (1/2) | 1.00 (3/3) | 0 | 1 | 0 | 40 |
<!-- scorer-table:end -->

## Running against a live model

Any OpenAI-compatible chat-completions endpoint works, local or hosted:

```bash
export AGENT_MODEL_BASE_URL=https://openrouter.ai/api/v1   # or http://localhost:11434/v1 for Ollama
export AGENT_MODEL_API_KEY=...                              # not needed for local servers
export AGENT_MODEL_NAME=qwen2.5:7b-instruct                 # default model for the demo

python -m evidence_ledger_agent demo --mode live --model openai/gpt-4.1-mini
python -m evidence_ledger_agent evaluate --config configs/live.yaml --require-live
python -m evidence_ledger_agent report --update-readme
```

With `--require-live`, or with a live config, the command exits with code 2 and a clear message if no endpoint is configured. It never falls back to the scripted replies. `configs/live.yaml` pins the model, overriding `AGENT_MODEL_NAME`, and its listed prices (0.40 and 1.60 USD per million input and output tokens). It caps each agent episode at 16 steps, 10 tool calls, 40,000 tokens and 300 seconds, and the whole run at 1.5 million tokens and 5 USD. The dollar cap is checked before every episode, and episodes skipped because a run cap was hit are recorded as failures, not dropped. Transient HTTP errors (429, 5xx, timeouts) are retried twice with backoff, and the retry count is saved with the run. The plain chat protocol (one JSON object per reply, no native tool calling) is deliberate, so that small local models can drive the same loop.

## Safety model

The model has no capability beyond five finite tools over an in-memory corpus: no shell, no code execution, no file writes, no network. Document text is untrusted data. The fixture corpus contains two documents with embedded instructions (one asks for the API key, one asks the reader to approve every claim and print credentials). Tests show that this text reaches the model only as delimited data, that it changes neither the allowlist nor the budget, and that a configured key never appears in a prompt or a trace. Gold labels live outside the package and are not reachable through any tool. Traces are sanitized for keys, bearer tokens and absolute paths before they are written. Details are in [docs/threat_model.md](docs/threat_model.md).

## Reproducibility

- Corpus documents are normalized and hashed. Loading fails if any document changes, and `scripts/freeze_corpus.py` re-records the hashes after a deliberate edit.
- Prompts are versioned (`ledger-prompts-v2`) and hashed. The prompt hash, config hash, corpus fingerprints, question, gold and script hashes, commit, agentcore version, model, token counts, cost, hardware and timestamps are written to each `run_meta.json` and carried into `reports/evidence.json`.
- The live pilot ran at commit `9d07e38` with agentcore 0.1.1. Checking out that commit and running the live command reproduces the protocol, though not necessarily the exact replies, since a hosted model can change behind a fixed id.
- Fixture runs are deterministic. A test runs the full evaluation twice and compares the ledgers and task results byte for byte, and another test checks that the demo reproduces the committed `reports/demo_ledger.json`.
- `reports/evidence.json` and `reports/evidence.md` are generated only from saved outputs. Modes without saved outputs are written as `pending`.
- The scripted replies are generated from readable plans by `scripts/make_fixture_scripts.py`.

## Limitations

- 24 fictional documents and 16 questions, written by the author. Useful for testing behaviour, too small and too self-made to rank models.
- The support overlap rule (at least half of the shorter span) and the substring check for conditions are simple, and both are documented in [docs/rubric.md](docs/rubric.md).
- The `conflicted` label covers both genuine disagreement and condition-dependent results. The rubric requires the condition to be named, but the scorer only checks for the term.
- If the process dies after a tool runs but before its result is checkpointed, that action runs again on resume. Every tool here is read-only, so this is harmless, and a tool with side effects would need to honour the idempotency key itself.
- Each live run covers 10 held-out questions; the gpt-4.1-mini runs use two runs per arm and the Sonnet run uses one. The v1 agent rows reflect the stricter 0.1.1 reply parser.
- The v1 and v2 numbers come from different question families, so the v1 to v2 change mixes the parser fix with a change of questions.

## Author

Aamir Malik

- GitHub: https://github.com/aamirmalik-dr
- LinkedIn: https://linkedin.com/in/aamirmalik-dr

## License

MIT, see [LICENSE](LICENSE). The corpus, questions and gold labels are original and released under the same license.
