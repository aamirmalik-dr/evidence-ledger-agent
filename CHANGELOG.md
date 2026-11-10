# Changelog

All live results were produced through OpenRouter at temperature 0. Counts are correct verdicts over episodes on held-out questions. Every version keeps the full history of saved outputs, so earlier results stay reproducible from the repository.

## 0.3.0 (2026-11-10)

v2 round, pre-registered in `docs/v2_preregistration.md`:
- New held-out family `heldout_v2`: 12 fictional perovskite documents and 10 questions, written after the parser fix was frozen.
- Live results with `openai/gpt-4.1-mini`, 10 questions x 2 runs:
  - single call 18/20
  - agent 16/20
  - agent without `expand_context` 15/20
  - lexical baseline 10/20
  - Malformed agent steps fell from 22 in v1 to 0.
- Live results with `anthropic/claude-sonnet-4.6`, 1 run: single call 10/10, agent 9/10.
- The first Sonnet attempt failed on HTTP 429 rate limits. It is kept under `reports/aborted/` and not counted.
- Saved model replies are written as ASCII-escaped JSON.

Figures:
- `scripts/make_figures.py` draws every figure from saved task results only.
- The current set: Figure 1 (accuracy by arm, paired difference against the single call, outcome composition, per-question tiles), Figure S1 (tool calls per episode) and Figure S2 (citation validity against accuracy).
  - Exported as SVG for the README and as 300 dpi PNG.
  - Wilson intervals for rates and a paired question-level bootstrap for differences (10,000 resamples, seed 20261109).
  - Every plotted value is in `docs/figures/figure_stats.json`.
  - The typeface, Liberation Sans, is vendored in `scripts/fonts/` under the SIL Open Font License.
- README:
  - "Main result" section with numbered captions, a Statistical methods paragraph and a Mermaid architecture diagram.
  - Two text corrections to match the saved data:
    - contradiction recall per arm;
    - the parser-fix sentence, which is now non-causal because v1 and v2 used different question families.
  - No result number changed.
- `tests/test_figures.py` checks that every figure is produced, stays within size limits and is byte-identical across runs.

## 0.2.0 (2026-11-09)

- agentcore 0.1.2: the reply parser reads the first complete JSON object and ignores trailing text. In v1, all 22 malformed agent steps were valid actions followed by an extra closing brace.
- v1 live pilot with `openai/gpt-4.1-mini`, 10 held-out questions x 2 runs, run at commit `9d07e38` with agentcore 0.1.1:
  - single call 18/20
  - agent 13/20
  - agent without `expand_context` 15/20
  - lexical baseline 8/20
- Headline and scorer-check tables are separate in the README and evidence report.
- Live configs take the adapter retry count and backoff per run.

## 0.1.0 (2026-11-09)

- agentcore 0.1.0 to 0.1.1:
  - typed schemas, a closed set of error codes, and fixture, replay and OpenAI-compatible adapters;
  - a policy layer with allowlist, argument schemas, budgets and idempotency keys;
  - an observe, decide, validate, execute, checkpoint loop with atomic checkpoints;
  - sanitized JSONL traces;
  - in 0.1.1, bounded retries, a pinned model id and provider-reported cost.
- Fictional 24-document corpus with hashes, BM25 retrieval, five typed tools (`search`, `read_span`, `expand_context`, `finish`, `abstain`) and a citation precheck for quote identity and provenance.
- Lexical and single-call baselines, a rubric scorer, an evaluation runner, evidence reports and a CLI (`demo`, `evaluate`, `report`, `verify`).
- Fixture mode with scripted replies and planted failures.
- Design, threat-model, rubric and data-manifest documents.
