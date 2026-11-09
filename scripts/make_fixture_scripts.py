"""Generate the scripted model replies used by the fixture adapter.

Fixture mode replays these replies instead of calling a model. They are
written by hand as compact plans below and expanded here into exact JSON
actions with offsets computed from the corpus. They exist to exercise the
loop, the policy and the scorer, including deliberate failure cases. They say
nothing about how well any real model performs.

Planted failure cases (documented in tests/fixtures/README.md):
- agent dev-q2: first finish uses a fabricated quote and is rejected, then corrected.
- agent dev-q4: final verdict "supported" based on an unsupported perspective.
- agent dev-q5: first reply is not JSON and needs the corrective re-prompt.
- agent ho-q05: never finishes and hits the tool-call cap.
- single_call dev-q2: the only citation paraphrases the source and fails validation.
- single_call ho-q02: verdict "supported" from the 80 C value only.

The agent_no_expand scripts are derived mechanically from the agent scripts:
every expand_context call becomes an equivalent read_span call.
"""

from __future__ import annotations

import json
from pathlib import Path

from evidence_ledger_agent.baselines import passages_for
from evidence_ledger_agent.citation_checks import CitationArg, resolve_citations
from evidence_ledger_agent.corpus import Corpus
from evidence_ledger_agent.evaluation import load_tasks
from evidence_ledger_agent.retrieval import BM25Index
from evidence_ledger_agent.schemas import SpanRef
from evidence_ledger_agent.tools import MAX_READ_CHARS

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"

# Plan steps: ("search", query[, filters]) | ("read", doc_id[, anchor, width])
#   | ("expand", radius) | ("finish", verdict, claim, [(doc_id, quote)], conditions, rationale)
#   | ("abstain", reason) | ("raw", text)
AGENT_PLANS: dict[str, dict[str, list[tuple]]] = {
    "dev": {
        "dev-q1": [
            ("search", "LX-4 stable 100 hours oxygen evolution"),
            ("read", "dev-01", "Results. All three", 300),
            ("expand", 500),
            ("search", "LX-4 stability near-neutral pH 7", {"pH": "7"}),
            ("read", "dev-02"),
            (
                "finish",
                "conflicted",
                "LX-4 is stable for 100 hours at pH 14 but deactivates within 12 hours at pH 7.",
                [
                    (
                        "dev-01",
                        "All three LX-4 electrodes remained stable for the full 100 hours at pH 14",
                    ),
                    ("dev-02", "At pH 7 the LX-4 electrodes were not stable"),
                ],
                {"pH": "stable at pH 14 (1 M KOH), not stable at pH 7 (phosphate buffer)"},
                "The two reports disagree, and the disagreement follows the electrolyte pH; "
                "the alkaline report explicitly limits its scope to strongly alkaline media.",
            ),
        ],
        "dev-q2": [
            ("search", "CM-2 current density 1.8 V flow cell"),
            ("read", "dev-03"),
            (
                "finish",
                "supported",
                "CM-2 sustains 620 mA cm-2 at 1.8 V.",
                [("dev-03", "sustained 620 mA cm-2 at a cell voltage of 1.8 V")],
                {},
                "Fabricated quote, planted to exercise the rejection path.",
            ),
            (
                "finish",
                "supported",
                "CM-2 sustained 0.62 A cm-2 (620 mA cm-2) at 1.8 V in a zero-gap flow cell.",
                [("dev-03", "the CM-2 anode sustained 0.62 A cm-2 at a cell voltage of 1.8 V")],
                {"cell": "zero-gap flow cell", "temperature": "60 °C", "electrolyte": "1 M KOH"},
                "0.62 A cm-2 equals 620 mA cm-2, above the 500 mA cm-2 threshold.",
            ),
        ],
        "dev-q3": [
            ("search", "RT-1 Faradaic efficiency oxygen evolution"),
            ("read", "dev-05"),
            ("search", "RT-1 correction Faradaic efficiency"),
            ("read", "dev-06"),
            (
                "finish",
                "insufficient",
                "The 99% value was corrected to 91%, so efficiency above 95% is not supported.",
                [
                    (
                        "dev-06",
                        "the corrected Faradaic efficiency of RT-1 for oxygen evolution is 91%, "
                        "not the 99% stated in the original report",
                    )
                ],
                {"electrolyte": "0.5 M sulfuric acid"},
                "A later correction supersedes the original 99% figure.",
            ),
        ],
        "dev-q4": [
            ("search", "LX-4 lattice-oxygen mechanism"),
            ("read", "dev-07"),
            (
                "finish",
                "supported",
                "LX-4 runs on the lattice-oxygen mechanism.",
                [
                    (
                        "dev-07",
                        "It is clear beyond reasonable doubt that LX-4 evolves oxygen "
                        "exclusively through the lattice-oxygen pathway",
                    )
                ],
                {},
                "Planted failure: accepts a confident perspective without data.",
            ),
        ],
        "dev-q5": [
            ("raw", "I should look for CM-2 data in acid first."),
            ("search", "CM-2 acidic electrolyte stability pH 1"),
            ("read", "dev-03"),
            ("search", "spinel catalyst acid stability"),
            (
                "abstain",
                "No document reports CM-2 in acidic electrolyte; the only acid data "
                "concern RT-1.",
            ),
        ],
        "dev-q6": [
            ("search", "CM-2 synthesis calcination temperature"),
            ("read", "dev-09"),
            (
                "finish",
                "supported",
                "CM-2 powder is made by calcining the dried gel in air at 450 °C.",
                [("dev-09", "calcined in air at 450 °C for 4 hours")],
                {"atmosphere": "air", "duration": "4 hours"},
                "The synthesis notebook states the calcination step directly.",
            ),
        ],
    },
    "heldout": {
        "ho-q01": [
            ("search", "GZ-9 ionic conductivity room temperature"),
            ("read", "ho-01"),
            (
                "finish",
                "supported",
                "GZ-9 conducts 1.2 mS cm-1 at 25 °C.",
                [("ho-01", "a total ionic conductivity of 1.2 mS cm-1 at 25 °C")],
                {"temperature": "25 °C", "atmosphere": "argon"},
                "Direct impedance measurement above the 1 mS cm-1 threshold.",
            ),
        ],
        "ho-q02": [
            ("search", "GZ-9 conductivity above 5 mS cm-1"),
            ("read", "ho-02", "Finding:", 200),
            ("expand", 300),
            ("read", "ho-01"),
            (
                "finish",
                "conflicted",
                "GZ-9 exceeds 5 mS cm-1 only at 80 °C; at 25 °C it is about 1.1 to 1.2 mS cm-1.",
                [
                    ("ho-02", "6.5 × 10-3 S cm-1 at 80 °C"),
                    ("ho-01", "a total ionic conductivity of 1.2 mS cm-1 at 25 °C"),
                ],
                {"temperature": "above 5 mS cm-1 at 80 °C only"},
                "6.5 × 10-3 S cm-1 is 6.5 mS cm-1, reached only at elevated temperature.",
            ),
        ],
        "ho-q03": [
            ("search", "AL-3 coating capacity retention 500 cycles"),
            ("read", "ho-04"),
            ("read", "ho-05"),
            (
                "finish",
                "insufficient",
                "The only supporting preprint was withdrawn.",
                [("ho-05", "are therefore unreliable and should not be cited")],
                {},
                "The withdrawal notice supersedes the retention values.",
            ),
        ],
        "ho-q04": [
            ("search", "SX-2 dry room stability 48 hours"),
            ("read", "ho-06"),
            (
                "finish",
                "supported",
                "SX-2 showed no degradation over 48 hours in a dry room.",
                [
                    (
                        "ho-06",
                        "SX-2 pellets showed no hydrogen sulfide release and no measurable "
                        "conductivity loss over 48 hours",
                    )
                ],
                {"humidity": "dry room, dew point -50 °C"},
                "Holds for dry-room conditions only; ambient air degrades SX-2.",
            ),
        ],
        "ho-q05": [
            ("search", "TQ-5 ionic conductivity"),
            ("read", "ho-09"),
            ("search", "TQ-5 replication"),
            ("read", "ho-08"),
            ("search", "TQ-5 argyrodite synthesis"),
            ("search", "TQ-5 cold pressing 370 MPa"),
            ("read", "ho-03"),
            ("search", "sulfide conductivity 25 °C"),
            ("read", "ho-06"),
            ("search", "TQ-5 discrepancy"),
            ("read", "ho-07"),
        ],
        "ho-q06": [
            ("search", "PB-1 binder oxidation stability 4.5 V"),
            ("read", "ho-10"),
            (
                "finish",
                "supported",
                "PB-1 shows no oxidation current up to 4.5 V vs Li/Li+.",
                [("ho-10", "showed no oxidation current above background up to 4.5 V vs Li/Li+")],
                {"method": "linear sweep voltammetry, 0.1 mV s-1", "source": "supplier datasheet"},
                "Supplier data, which the datasheet calls typical rather than a specification.",
            ),
        ],
        "ho-q07": [
            ("search", "GZ-9 lithium metal cycling 1000 cycles"),
            ("read", "ho-12"),
            (
                "finish",
                "insufficient",
                "Only 200 stable cycles are reported; nothing beyond.",
                [("ho-12", "the study stopped at 200 cycles")],
                {"stack pressure": "5 MPa"},
                "No data exist for more than 200 cycles.",
            ),
        ],
        "ho-q08": [
            ("search", "GZ-9 dendrite grain-boundary electronic conductivity"),
            ("read", "ho-11"),
            (
                "finish",
                "insufficient",
                "The cause is asserted in an opinion piece without data.",
                [
                    (
                        "ho-11",
                        "We have not measured the electronic conductivity of GZ-9 grain boundaries",
                    )
                ],
                {},
                "The only source is an opinion that reports no measurements.",
            ),
        ],
        "ho-q09": [
            ("search", "SX-2 area-specific resistance interface"),
            ("read", "ho-07"),
            (
                "finish",
                "supported",
                "The SX-2 interfacial ASR is 35 ohm cm2 at 25 °C.",
                [("ho-07", "the interfacial ASR of SX-2 was 0.035 kΩ cm2 at 25 °C")],
                {
                    "temperature": "25 °C",
                    "electrodes": "lithium-indium",
                    "stack pressure": "10 MPa",
                },
                "0.035 kOhm cm2 equals 35 Ohm cm2, below 50.",
            ),
        ],
        "ho-q10": [
            ("search", "SX-2 hydrogen sulfide humidity"),
            ("read", "ho-06"),
            (
                "finish",
                "supported",
                "SX-2 releases H2S within 2 minutes at 30% relative humidity.",
                [
                    (
                        "ho-06",
                        "at 30% relative humidity and 25 °C, SX-2 released detectable hydrogen "
                        "sulfide within 2 minutes",
                    )
                ],
                {"humidity": "30% RH", "temperature": "25 °C"},
                "Direct statement.",
            ),
        ],
    },
}

# Single-call answers: (verdict, claim, [(doc_id, quote)], conditions, rationale) or ("abstain", r)
SINGLE_PLANS: dict[str, dict[str, tuple]] = {
    "dev": {
        "dev-q1": (
            "conflicted",
            "Stable at pH 14 for 100 hours, unstable at pH 7.",
            [
                (
                    "dev-01",
                    "All three LX-4 electrodes remained stable for the full 100 hours at pH 14",
                ),
                ("dev-02", "At pH 7 the LX-4 electrodes were not stable"),
            ],
            {"pH": "14 versus 7"},
            "Results depend on pH.",
        ),
        "dev-q2": (
            "supported",
            "CM-2 reaches 620 mA cm-2 at 1.8 V.",
            [("dev-03", "sustained 620 mA cm-2 at 1.8 V")],
            {},
            "Planted failure: paraphrased quote.",
        ),
        "dev-q3": (
            "insufficient",
            "Corrected to 91%.",
            [("dev-06", "the corrected Faradaic efficiency of RT-1 for oxygen evolution is 91%")],
            {},
            "The correction supersedes 99%.",
        ),
        "dev-q4": (
            "insufficient",
            "The isotope test was inconclusive.",
            [("dev-08", "the experiment is inconclusive")],
            {},
            "No direct evidence.",
        ),
        "dev-q5": ("abstain", "No passage covers CM-2 in acid."),
        "dev-q6": (
            "supported",
            "Calcined at 450 °C in air.",
            [("dev-09", "calcined in air at 450 °C for 4 hours")],
            {},
            "Stated directly.",
        ),
    },
    "heldout": {
        "ho-q01": (
            "supported",
            "1.2 mS cm-1 at 25 °C.",
            [("ho-01", "a total ionic conductivity of 1.2 mS cm-1 at 25 °C")],
            {"temperature": "25 °C"},
            "Above 1 mS cm-1.",
        ),
        "ho-q02": (
            "supported",
            "GZ-9 reaches 6.5 mS cm-1.",
            [("ho-02", "6.5 × 10-3 S cm-1 at 80 °C")],
            {},
            "Planted failure: ignores the temperature condition.",
        ),
        "ho-q03": (
            "insufficient",
            "Preprint withdrawn.",
            [("ho-05", "are therefore unreliable and should not be cited")],
            {},
            "Withdrawn data.",
        ),
        "ho-q04": (
            "supported",
            "Stable 48 hours in a dry room.",
            [("ho-06", "no measurable conductivity loss over 48 hours")],
            {"humidity": "dry room"},
            "Stated directly.",
        ),
        "ho-q05": (
            "conflicted",
            "3.1 versus 0.9 mS cm-1 at 25 °C.",
            [
                ("ho-09", "gave an ionic conductivity of 3.1 mS cm-1"),
                ("ho-08", "TQ-5 showed an ionic conductivity of 0.9 mS cm-1 at 25 °C"),
            ],
            {"temperature": "25 °C"},
            "Replication disagrees.",
        ),
        "ho-q06": (
            "supported",
            "Stable to 4.5 V.",
            [("ho-10", "no oxidation current above background up to 4.5 V vs Li/Li+")],
            {},
            "Datasheet value.",
        ),
        "ho-q07": ("abstain", "No passage reports 1000 cycles."),
        "ho-q08": (
            "insufficient",
            "Opinion without measurements.",
            [
                (
                    "ho-11",
                    "We have not measured the electronic conductivity of GZ-9 grain boundaries",
                )
            ],
            {},
            "No data.",
        ),
        "ho-q09": (
            "supported",
            "35 ohm cm2 at 25 °C.",
            [("ho-07", "the interfacial ASR of SX-2 was 0.035 kΩ cm2 at 25 °C")],
            {"temperature": "25 °C"},
            "0.035 kOhm cm2 is 35 Ohm cm2.",
        ),
        "ho-q10": (
            "supported",
            "H2S within 2 minutes at 30% RH.",
            [("ho-06", "SX-2 released detectable hydrogen sulfide within 2 minutes")],
            {"humidity": "30% RH"},
            "Stated directly.",
        ),
    },
}


def _act(summary: str, tool: str, **arguments) -> str:
    return json.dumps(
        {"summary": summary, "action": {"tool": tool, "arguments": arguments}}, ensure_ascii=False
    )


def expand_agent_plan(corpus: Corpus, plan: list[tuple], allow_expand: bool) -> list[str]:
    """Turn a plan into raw replies, tracking which spans have been read."""
    replies: list[str] = []
    read: list[SpanRef] = []
    for step in plan:
        kind = step[0]
        if kind == "raw":
            replies.append(step[1])
        elif kind == "search":
            filters = step[2] if len(step) > 2 else {}
            replies.append(
                _act(
                    f"Search the corpus for: {step[1]}.",
                    "search",
                    query=step[1],
                    filters=filters,
                    limit=5,
                )
            )
        elif kind == "read":
            doc = corpus.get(step[1])
            if len(step) > 2:
                start = doc.text.index(step[2])
                end = min(len(doc.text), start + step[3])
            else:
                start, end = 0, min(len(doc.text), MAX_READ_CHARS)
            read.append(SpanRef(doc_id=doc.doc_id, start=start, end=end, doc_hash=doc.sha256))
            replies.append(
                _act(
                    f"Read {doc.doc_id} to check its wording.",
                    "read_span",
                    doc_id=doc.doc_id,
                    start=start,
                    end=end,
                )
            )
        elif kind == "expand":
            last = read[-1]
            doc = corpus.get(last.doc_id)
            start, end = max(0, last.start - step[1]), min(len(doc.text), last.end + step[1])
            read.append(SpanRef(doc_id=doc.doc_id, start=start, end=end, doc_hash=doc.sha256))
            if allow_expand:
                replies.append(
                    _act(
                        "Expand the span to see its scope and caveats.",
                        "expand_context",
                        span_id=last.span_id,
                        radius=step[1],
                    )
                )
            else:
                replies.append(
                    _act(
                        "Read a wider window to see its scope and caveats.",
                        "read_span",
                        doc_id=doc.doc_id,
                        start=start,
                        end=end,
                    )
                )
        elif kind == "finish":
            _, verdict, claim, quotes, conditions, rationale = step
            citations = []
            for doc_id, quote in quotes:
                span = next((s for s in reversed(read) if s.doc_id == doc_id), None)
                if span is None:
                    raise ValueError(f"plan cites {doc_id} before reading it")
                citations.append({"span_id": span.span_id, "quote": quote})
            replies.append(
                _act(
                    f"Finish with verdict {verdict}.",
                    "finish",
                    verdict=verdict,
                    claim=claim,
                    citations=citations,
                    conditions=conditions,
                    rationale=rationale,
                )
            )
        elif kind == "abstain":
            replies.append(
                _act("Abstain, the corpus does not bear on the claim.", "abstain", reason=step[1])
            )
    return replies


def single_reply(corpus: Corpus, index: BM25Index, task, plan: tuple, top_k: int) -> str:
    """Raw reply for the single-call baseline, citing only passages it was shown."""
    if plan[0] == "abstain":
        return json.dumps({"abstain": plan[1]})
    verdict, claim, quotes, conditions, rationale = plan
    passages = {p["doc_id"]: p for p in passages_for(task, corpus, index, top_k)}
    cits = []
    for doc_id, quote in quotes:
        if doc_id not in passages:
            raise ValueError(f"{task.task_id}: {doc_id} is not among the top-{top_k} passages")
        cits.append({"span_id": passages[doc_id]["span_id"], "quote": quote})
    return json.dumps(
        {
            "verdict": verdict,
            "claim": claim,
            "citations": cits,
            "conditions": conditions,
            "rationale": rationale,
        },
        ensure_ascii=False,
    )


def _check_quotes(corpus: Corpus, plans: dict[str, list[tuple]]) -> None:
    """Every finish quote must resolve, except the planted fabricated one."""
    for task_id, plan in plans.items():
        for step in plan:
            if step[0] != "finish" or "Fabricated" in step[5]:
                continue
            for doc_id, quote in step[3]:
                doc = corpus.get(doc_id)
                ref = SpanRef(doc_id=doc_id, start=0, end=len(doc.text), doc_hash=doc.sha256)
                ok, _ = resolve_citations(
                    corpus, [ref], [CitationArg(span_id=ref.span_id, quote=quote)]
                )
                if not ok:
                    raise ValueError(f"{task_id}: quote not found in {doc_id}: {quote}")


def main(top_k: int = 4) -> None:
    """Write tests/fixtures/scripts/<family>_<arm>.json for all scripted arms."""
    out_dir = FIX / "scripts"
    out_dir.mkdir(parents=True, exist_ok=True)
    for family in ("dev", "heldout"):
        corpus = Corpus.load(FIX / "corpus" / family)
        index = BM25Index(corpus)
        tasks = {t.task_id: t for t in load_tasks(FIX / f"questions_{family}.json")}
        _check_quotes(corpus, AGENT_PLANS[family])
        outputs = {
            "agent": {
                k: expand_agent_plan(corpus, p, True) for k, p in AGENT_PLANS[family].items()
            },
            "agent_no_expand": {
                k: expand_agent_plan(corpus, p, False) for k, p in AGENT_PLANS[family].items()
            },
            "single_call": {
                k: [single_reply(corpus, index, tasks[k], p, top_k)]
                for k, p in SINGLE_PLANS[family].items()
            },
        }
        for arm, scripts in outputs.items():
            path = out_dir / f"{family}_{arm}.json"
            path.write_text(
                json.dumps(scripts, indent=1, ensure_ascii=False) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(f"wrote {path.relative_to(ROOT)} ({len(scripts)} tasks)")


if __name__ == "__main__":
    main()
