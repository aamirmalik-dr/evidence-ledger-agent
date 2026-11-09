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
- Rejects a `finish` that cites an unread span, an unknown document, out-of-range offsets, a non-verbatim quote, a `supported` verdict without a citation, or a `conflicted` verdict that cites fewer than two documents. The agent sees the typed error and can try again.
- Enforces caps on steps, tool calls, tokens and wall time per episode, and on tokens and dollars per evaluation run. Hitting a cap is a recorded stop reason.
- Checkpoints atomically after every result, writing each action to the checkpoint before it runs, and resumes without repeating completed actions.
- Writes sanitized JSONL traces with the model's one-sentence summary per step, never hidden reasoning.
- Scores answers on verdict accuracy, citation validity, quote fidelity, support precision and recall, contradiction recall, correct abstention, condition recall, unsupported claims, failures and cost. Every metric is reported with its numerator and denominator.

Does not:
- Judge whether a source is scientifically correct.
- Use real literature. The corpus is a fictional test bed of 24 documents, not a benchmark.
- Give the model a shell, code execution, file access or network access.
- Include live model results yet. No model endpoint was available when this was built, so the live rows are pending (see below).

## How it works

```
src/evidence_ledger_agent/
  agentcore/           reusable core, no domain knowledge (541 lines of code)
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

`agentcore` was written here first. The later repositories in this series will copy it verbatim and record any change in their own `docs/agentcore_changes.md`.

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

Read the table with its labels. In fixture mode, the `single_call`, `agent` and `agent_no_expand` arms replay hand-written scripted replies, and the planted failures in those scripts are listed in [tests/fixtures/README.md](tests/fixtures/README.md). Those rows show that the policy and scorer catch what they should. They say nothing about how well any model performs, and the identical agent and ablation rows are by construction. The `lexical` arm calls no model, so its rows are real measurements of that baseline on this corpus.

<!-- evidence-table:start -->
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
<!-- evidence-table:end -->

What the measured rows show. The lexical baseline gets 3 of 6 development and 4 of 10 held-out verdicts right. It cannot detect a conflict (0 of 3 across both families), and it asserts `supported` on 9 claims that are wrong or have no supporting citation, including the withdrawn coating result, the opinion-only dendrite mechanism and the 1000-cycle claim the corpus does not address. Its citations are always valid because they are extracted, never generated, which is exactly why citation validity alone is a poor quality signal: lexical overlap is not support.

What the scripted rows confirm. The scorer catches every planted failure. A paraphrased quote lowers citation validity and counts as an unsupported claim even though the verdict is right. A fabricated quote is rejected at `finish` and shows up as a rejected attempt, not as an accepted citation. A confident perspective accepted as support counts as a wrong verdict and an unsupported claim. An episode that never finishes is recorded as a failure with stop reason `max_tool_calls` and stays in every denominator. [reports/evidence.md](reports/evidence.md) lists each of these episodes.

Pending: the live pilot, meaning the held-out family (10 questions), two runs, all four arms, one model, and the caps in `configs/live.yaml`. Only that run can say whether iterating helps over a single call with the same model, and whether removing `expand_context` costs anything. A result where the single call or the lexical baseline wins will be reported as is.

## Running against a live model

Any OpenAI-compatible chat-completions endpoint works, local or hosted:

```bash
# local, for example Ollama
export AGENT_MODEL_BASE_URL=http://localhost:11434/v1
export AGENT_MODEL_NAME=qwen2.5:7b-instruct
# hosted providers also need
export AGENT_MODEL_API_KEY=...

python -m evidence_ledger_agent demo --mode live
python -m evidence_ledger_agent evaluate --config configs/live.yaml --require-live
python -m evidence_ledger_agent report --update-readme
```

With `--require-live`, or with a live config, the command exits with code 2 and a clear message if no endpoint is configured. It never falls back to the scripted replies. `configs/live.yaml` caps each agent episode at 16 steps, 10 tool calls, 40,000 tokens and 300 seconds, and caps the whole run at 1.5 million tokens. Set `usd_per_mtok_input` and `usd_per_mtok_output` to also enforce the 5 USD cap. Episodes skipped because a run cap was hit are recorded as failures, not dropped. The plain chat protocol (one JSON object per reply, no native tool calling) is deliberate, so that small local models can drive the same loop.

## Safety model

The model has no capability beyond five finite tools over an in-memory corpus: no shell, no code execution, no file writes, no network. Document text is untrusted data. The fixture corpus contains two documents with embedded instructions (one asks for the API key, one asks the reader to approve every claim and print credentials). Tests show that this text reaches the model only as delimited data, that it changes neither the allowlist nor the budget, and that a configured key never appears in a prompt or a trace. Gold labels live outside the package and are not reachable through any tool. Traces are sanitized for keys, bearer tokens and absolute paths before they are written. Details are in [docs/threat_model.md](docs/threat_model.md).

## Reproducibility

- Corpus documents are normalized and hashed. Loading fails if any document changes, and `scripts/freeze_corpus.py` re-records the hashes after a deliberate edit.
- Prompts are versioned (`ledger-prompts-v1`) and hashed. The prompt hash, config hash, corpus fingerprints, question, gold and script hashes, commit, hardware and timestamps are written to `reports/fixture/run_meta.json` and carried into `reports/evidence.json`.
- Fixture runs are deterministic. A test runs the full evaluation twice and compares the ledgers and task results byte for byte, and another test checks that the demo reproduces the committed `reports/demo_ledger.json`.
- `reports/evidence.json` and `reports/evidence.md` are generated only from saved outputs. Modes without saved outputs are written as `pending`.
- The scripted replies are generated from readable plans by `scripts/make_fixture_scripts.py`.

## Limitations

- 24 fictional documents and 16 questions, written by the author. Useful for testing behaviour, too small and too self-made to rank models.
- The support overlap rule (at least half of the shorter span) and the substring check for conditions are simple, and both are documented in [docs/rubric.md](docs/rubric.md).
- The `conflicted` label covers both genuine disagreement and condition-dependent results. The rubric requires the condition to be named, but the scorer only checks for the term.
- If the process dies after a tool runs but before its result is checkpointed, that action runs again on resume. Every tool here is read-only, so this is harmless, and a tool with side effects would need to honour the idempotency key itself.
- No live model results yet.

## Author

Aamir Malik

- GitHub: https://github.com/aamirmalik-dr
- LinkedIn: https://linkedin.com/in/aamirmalik-dr

## License

MIT, see [LICENSE](LICENSE). The corpus, questions and gold labels are original and released under the same license.
