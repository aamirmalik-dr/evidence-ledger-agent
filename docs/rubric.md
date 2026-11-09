# Rubric

Frozen 2026-11-09 in `evaluator/gold_dev.json` (`gold-dev-v1`) and `evaluator/gold_heldout.json` (`gold-heldout-v1`), before any evaluation run. The held-out family was written and frozen before any prompt work. If held-out outcomes are ever inspected and then used to change prompts, tools or thresholds, that held-out version retires to development and a new held-out family is written.

## Gold record per question

| Field | Meaning |
|---|---|
| `verdict` | `supported`, `conflicted` or `insufficient` |
| `abstain_acceptable` | whether `abstain` also counts as a correct outcome |
| `required` | groups of text anchors; each group must be covered by at least one citation for full recall. Alternatives inside a group are equivalent (for example two documents stating the same value). |
| `acceptable` | further anchors that count as supporting for precision but are not required |
| `condition_terms` | groups of alternative terms; a group is found when any term appears in the answer's conditions, claim or rationale |

Anchors are stored as text and resolved to offsets at load time; loading fails unless each anchor occurs exactly once in its document.

## Verdict definitions

- `supported`: the corpus directly supports the claim as stated, under the stated conditions.
- `conflicted`: credible documents disagree about the claim. This includes condition-dependent evidence, where the claim holds under one condition and fails under another, and the answer must record the condition (pH, temperature). It also includes genuine conflicts under the same conditions, such as a failed replication.
- `insufficient`: the corpus does not adequately support the claim as stated, including support that was corrected, superseded or withdrawn, support that is only asserted without data, and questions the corpus does not address.
- `abstain` is the agent's way to stop without a verdict. It is scored correct only where `abstain_acceptable` is true. Where the corpus settles the question (for example a correction notice gives the true value), abstaining is wrong.

## Metrics

All metrics are reported per family and arm with numerator and denominator. Every episode counts, including failures, refusals, malformed output and budget stops.

| Metric | Numerator | Denominator |
|---|---|---|
| Verdict accuracy | correct outcomes | all episodes |
| Citation validity | citations that pass the provenance checks | all citations the arm emitted, including those in rejected `finish` attempts |
| Quote fidelity | emitted citations without a quote mismatch | all emitted citations |
| Support precision | accepted citations that overlap a gold anchor, counted only when the verdict is correct | accepted citations |
| Support recall | required groups covered, counted only when the verdict is correct | required groups |
| Contradiction recall | gold-conflicted episodes answered `conflicted` with every required group covered | gold-conflicted episodes |
| Correct abstention | episodes answered `abstain` or `insufficient` | episodes where abstention is acceptable |
| Condition recall | condition groups found | condition groups |
| Unsupported claims | count of `supported` or `conflicted` answers that are wrong or have no supporting citation | |
| Failures | count of episodes with no answer (budget stop, adapter error, malformed output) | |
| Cost | tool calls, model calls, prompt characters, tokens (live only), wall time (live only) | |

A citation supports when it lies in the same document as an anchor and their overlap is at least half the length of the shorter of the two. A valid quote attached to a wrong verdict never counts as support.

## Thresholds

No success threshold is defined. The comparison is descriptive, and the agent is not required to beat the baselines. The only tuned-looking number in the system, the lexical baseline's coverage threshold of 0.5, was written into `configs/fixture.yaml` and `configs/live.yaml` before the first evaluation run and has not been changed.
