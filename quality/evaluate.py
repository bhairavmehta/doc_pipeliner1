"""
Score documents against a gold document – the regression suite for prompts, models and critics.

    # one document, with the story's findings and story text
    python quality/evaluate.py newdoc.docx --findings research/research_findings.md --story 311617_story.md

    # compare several documents (e.g. before / after a prompt change) and save the table
    python quality/evaluate.py stories/311617/content.md old_run/content.md --findings ... --story ... --csv scores.csv

    # fail (exit 3) if any score dropped compared with a saved baseline
    python quality/evaluate.py stories/*/content.md --baseline scores_baseline.json --save scores_now.json

    # add the J1 judge (needs JUDGE_* or LLM_* settings)
    python quality/evaluate.py newdoc.docx --findings ... --story ... --judge

Default gold document: examples/gold/US311617/US311617_benchmark.md (change with --gold).
"""
import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from quality import critics as C  # noqa: E402
from quality import facts as K1  # noqa: E402
from quality import scorecard as S  # noqa: E402
from quality.doc_model import load  # noqa: E402

DEFAULT_GOLD = HERE.parent / "examples" / "gold" / "US311617" / "US311617_benchmark.md"


def score_file(path, facts, sources, story, gold, mode="rules", judge=False, fig_report=None, plan=None, sources_dir=None):
    doc = load(path)
    pages = C.load_source_pages(sources_dir) if sources_dir else {}
    ctx = C.Context(doc, facts, sources, story=story, gold=gold, mode=mode, plan=plan, source_pages=pages,
                    source_dir=sources_dir)
    return S.evaluate(ctx, fig_report=fig_report, judge=judge)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docs", nargs="+", help=".md or .docx documents to score")
    ap.add_argument("--findings", help="research_findings.md the documents were written from")
    ap.add_argument("--story", help="the user story file")
    ap.add_argument("--gold", default=str(DEFAULT_GOLD))
    ap.add_argument("--sources", help="research/sources folder (for citation checks)")
    ap.add_argument("--mode", choices=["rules", "hybrid"], default="rules", help="hybrid = rules + small model (SLM_*)")
    ap.add_argument("--judge", action="store_true", help="run the J1 pairwise judge against the gold document")
    ap.add_argument("--report", help="write a Markdown scorecard for the first document to this path")
    ap.add_argument("--csv", help="write a summary table")
    ap.add_argument("--save", help="save scores as JSON (use as a later --baseline)")
    ap.add_argument("--baseline", help="JSON from an earlier --save; exit 3 if a score dropped")
    a = ap.parse_args()

    facts, sources = K1.build(Path(a.findings).read_text(encoding="utf-8")) if a.findings else ([], [])
    story = Path(a.story).read_text(encoding="utf-8") if a.story else ""
    gold = load(a.gold) if a.gold and Path(a.gold).exists() else None
    rows, saved = [], {}
    for i, p in enumerate(a.docs):
        card, findings = score_file(p, facts, sources, story, gold, a.mode, a.judge,
                                    sources_dir=Path(a.sources) if a.sources else None)
        d = card["dimensions"]
        rows.append({"doc": p, "pass": card["pass"], "vs_gold": card["relative_to_gold"], "overall": card["overall"],
                     "words": card["counts"]["words"], "requirements": card["counts"]["requirements"],
                     "high": card["counts"]["high"], **d})
        saved[p] = {"overall": card["overall"], "vs_gold": card["relative_to_gold"], **d}
        if i == 0 and a.report:
            Path(a.report).write_text(S.to_markdown(card, findings, f"Quality scorecard – {Path(p).name}"), encoding="utf-8")
    keys = ["pass", "vs_gold", "overall", "words", "requirements", "high"] + list(rows[0].keys())[7:]
    w = max(len(Path(r["doc"]).name) for r in rows) + 2
    print("doc".ljust(w) + "".join(k.replace("_", " ")[:14].ljust(15) for k in keys))
    for r in rows:
        print(Path(r["doc"]).name.ljust(w) + "".join(("–" if r[k] is None else str(r[k]))[:14].ljust(15) for k in keys))
    if gold:
        print(f"\n(gold: {Path(a.gold).name}; 'vs gold' compares {', '.join(S.STORY_INDEPENDENT)})")
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
    if a.save:
        Path(a.save).write_text(json.dumps(saved, indent=2), encoding="utf-8")
    if a.baseline:
        base = json.loads(Path(a.baseline).read_text(encoding="utf-8"))
        drops = []
        for doc, sc in saved.items():
            for k, v in sc.items():
                b = base.get(doc, {}).get(k)
                if v is not None and b is not None and v < b - 0.02:
                    drops.append(f"{doc}: {k} {b} -> {v}")
        if drops:
            print("\nREGRESSIONS:\n  " + "\n  ".join(drops))
            sys.exit(3)
        print("\nNo regressions against the baseline.")


if __name__ == "__main__":
    main()
