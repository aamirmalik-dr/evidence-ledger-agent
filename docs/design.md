# Design

## The question the system answers

Given a narrow claim ("LX-4 is stable for 100 hours of oxygen evolution") and a local corpus, decide whether the corpus supports it, under which conditions, and prove every quoted word. The output is a ledger entry, not an essay: a verdict, a one-line claim, the conditions under which it holds, a short rationale, and citations that each carry a document id, character offsets, the document hash and the verbatim quote.

## What makes it an agent

The model picks every tool call from the results of earlier calls, and it decides when to finish or abstain. Nothing in the code fixes the sequence of searches and reads. Everything that limits the model sits outside it:

| Concern | Where it lives |
|---|---|
| Which tools exist, their argument schemas | `tools.py`, `agentcore/policy.py` (`ToolRegistry`, allowlist) |
| Argument validation | pydantic models per tool, checked before execution |
| Budgets (steps, tool calls, tokens, wall time) | `agentcore/policy.py` (`Budget`, `Policy.budget_stop`) |
| Citation provenance | `citation_checks.py`, enforced as a precheck on `finish` |
| Scoring | `evaluation.py` with labels from `evaluator/`, never visible to the agent |

## Loop

```
            +--------------------------------------------------------------+
            |  observable state + last k tool results (untrusted data)     |
            v                                                              |
   model ---> one JSON decision ---> parse (1 corrective re-prompt) -------+
                                          |
                                          v
                        write-ahead checkpoint (pending action)
                                          |
                    validate: allowlist, schema, precheck (finish)
                                          |
                     execute tool ---> result appended to history
                                          |
                     checkpoint (atomic) + trace event (sanitized)
                                          |
                  terminal tool? -> complete / abstained ; cap hit? -> stopped
```

Each step the model receives a system prompt (role, rules, verdict definitions, JSON schemas of the allowed tools), a compact observable state (question, stated conditions, documents seen, span ids read, steps and tool calls left, rejected finish attempts) and the last four tool results wrapped in `<tool_result trust="untrusted-data">` blocks. It must answer with exactly one object, `{"summary": ..., "action": {"tool": ..., "arguments": {...}}}`. The one-sentence summary is stored in the trace; hidden reasoning is never requested or stored. Plain chat completion is used instead of provider tool calling so that small local models can drive the same loop.

## Tools

| Tool | Bound | Returns |
|---|---|---|
| `search(query, filters, limit)` | limit at most 10 | ranked ids, scores, 200-character snippets, manifest metadata (title, kind, date, conditions, supersedes). Never labels. |
| `read_span(doc_id, start, end)` | at most 1500 characters | text, `span_id` (`doc:start:end`), document hash |
| `expand_context(span_id, radius)` | radius at most 500, only on a span already read | wider text with new offsets |
| `finish(verdict, claim, citations, conditions, rationale)` | rationale at most 80 words, at most 8 citations | the ledger record |
| `abstain(reason)` | | ends the episode without a verdict |

A citation is a `span_id` the agent has read plus a quote copied from inside it. The precheck on `finish` rejects the call (a typed `precondition_failed` error the agent can recover from) when a span was never read, the document is unknown, the offsets are out of range, the quote is not verbatim text of that span, a `supported` verdict has no citation, or a `conflicted` verdict cites fewer than two documents. Accepted quotes are re-anchored to their exact offsets inside the document, so the ledger points at the quote, not at the whole read window.

## Corpus and retrieval

Documents are normalized once (NFC, Unix newlines, no trailing whitespace, at most one blank line in a row), hashed with SHA-256 and held in a read-only mapping. Offsets are Python string indices, so they count Unicode code points; `°`, `×` and `Ω` are one character each. The manifest stores every hash, and loading fails if any document changed.

Retrieval is Okapi BM25 (k1 = 1.5, b = 0.75) over lower-cased tokens that keep compounds such as `LX-4`, `0.62` and `cm-2` whole while also indexing their parts. Ties are broken by document id, so search is deterministic.

## Checkpoints and resume

The loop writes the validated action to the checkpoint before executing it (write-ahead), then writes again after the result. Each write goes to a temporary file, is fsynced and is renamed over the checkpoint after the previous checkpoint has been moved to `.prev`. Each file stores a SHA-256 of its payload, so a truncated or edited file is detected and the previous version is loaded instead.

On resume the loop positions a scripted adapter at the number of model calls already made, executes a pending action that has no result (without asking the model again), and skips any action whose idempotency key already has a result in history. Tests cover a crash after a retrieval step, a crash after a rejected finish, a crash between the write-ahead and the tool result, and a truncated checkpoint.

One gap is stated plainly: if the process dies after a tool has run but before the post-result checkpoint, the action runs again on resume. Every tool here is read-only, so this is harmless. A tool with real side effects would need to honour the idempotency key itself; the policy only deduplicates against recorded history.

## Baselines and ablation

| Arm | Model | Information | Decision |
|---|---|---|---|
| `lexical` | none | BM25 top document | best sentence by query-term coverage; `supported` if coverage is at least 0.5 (fixed in the config before any run), else `insufficient` |
| `single_call` | same as agent | BM25 top 4 documents, first 1500 characters each | one reply with verdict and citations; one corrective re-prompt on malformed output; citations checked against the passages shown |
| `agent` | same | whole corpus through tools | iterative loop above |
| `agent_no_expand` | same | same, without `expand_context` | ablation: can the agent recover qualifying context with reads alone |

Budgets per agent episode: 16 steps, 10 tool calls, 40,000 tokens, 300 seconds.

## agentcore

`agentcore/` is the reusable part: `schemas.py` (typed actions, results, a closed set of error codes, stop reasons, `BaseAgentState`), `adapters.py` (adapter protocol, fixture, replay and OpenAI-compatible adapters), `policy.py` (registry, allowlist, validation, budgets, idempotency), `loop.py` (loop, checkpoint store, decision parser) and `trace.py` (sanitized JSONL traces). It has no dependency on the evidence-ledger domain and is copied verbatim into later projects. It is 541 lines of code, 794 lines including docstrings and blank lines, against a target of 600 lines of code.
