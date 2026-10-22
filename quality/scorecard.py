"""
Scorecard: turns critic metrics into the 10-dimension rubric (D1–D10), applies the gates in gates.json
and compares the draft with a gold document.

D1 ask coverage · D2 fact recall · D3 factual precision · D4 requirement depth (checklists + floors)
D5 requirement quality · D6 specificity · D7 decision quality · D8 citations · D9 figures · D10 judge (optional)

The judge (J1) is optional. It runs a pairwise comparison against the gold document, one dimension at a time and
in both orders (to cancel position bias). Its raw win rate is mapped to a probability with Platt scaling
when quality/calibration.json exists ({"a": ..., "b": ...}, fitted on SME-scored documents).
"""
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from quality import critics as C  # noqa: E402
from quality import slm  # noqa: E402

GATES = HERE / "gates.json"
CALIBRATION = HERE / "calibration.json"
JUDGE_PROMPT = HERE.parent / "prompts" / "7_judge.md"
JUDGE_DIMENSIONS = {
    "requirements": "Requirements are testable, specific (numbers, named artifacts, rules) and complete for each topic the "
                    "story asks about; no vague verbs such as 'handle' or 'maintain'.",
    "evidence": "Facts, versions, codes and numbers come from the research and are cited to real sources; caveats are kept.",
    "decisions": "Each open question gets concrete options with pros and cons, one clear recommendation with steps, "
                 "and a way for the team to agree.",
    "domain_completeness": "Covers what an expert would expect beyond the literal asks: versioning, reruns, roles, "
                           "acceptance targets, governance.",
}


def load_gates():
    return json.loads(GATES.read_text(encoding="utf-8"))


def _norm(metrics, fig_report=None, judge=None):
    m1, m2, m3, m4, m6, m7, m8 = (metrics.get(k, {}) for k in ("C1", "C2", "C3", "C4", "C6", "C7", "C8"))
    secs = [s for s in m3.get("sections", []) if s.get("floor")]
    floor_share = sum(1 for s in secs if s["requirements"] >= s["floor"]) / len(secs) if secs else 0.0
    d = {
        "D1_ask_coverage": m3.get("ask_coverage"),
        "D2_fact_recall": m3.get("fact_recall"),
        "D3_precision": m2.get("precision"),
        "D4_depth": round(0.5 * m3.get("checklist_coverage", 0) + 0.5 * floor_share, 3),
        "D5_req_quality": m1.get("mean_score"),
        "D6_specificity": m4.get("relative_density") if m4.get("relative_density") is not None
        else round(min(1.0, m4.get("density", 0) / 9.0), 3),
        "D7_decisions": m6.get("pass_rate"),
        "D8_citations": round(0.5 * (1.0 if m7.get("internal", 0) == 0 and m7.get("unresolved", 0) == 0 else 0.0)
                              + 0.5 * (m7.get("source_recall") if m7.get("source_recall") is not None else 1.0), 3),
        "D9_figures": None,
        "D10_judge": judge.get("probability") if judge else None,
    }
    if fig_report is not None:
        high = fig_report.get("high", 0)
        d["D9_figures"] = round(max(0.0, 1 - 0.2 * high), 3)
    return d


def gate_results(dims, metrics, fig_report=None, gates=None):
    g = gates or load_gates()
    m2, m3, m7 = metrics.get("C2", {}), metrics.get("C3", {}), metrics.get("C7", {})
    res = {}

    def put(key, ok, why):
        res[key] = {"pass": bool(ok), "hard": g[key].get("hard", False), "why": why}

    if dims["D1_ask_coverage"] is not None:
        put("D1_ask_coverage", dims["D1_ask_coverage"] >= g["D1_ask_coverage"]["min"], f"{dims['D1_ask_coverage']:.0%} of asks covered")
    if dims["D2_fact_recall"] is not None:
        put("D2_fact_recall", dims["D2_fact_recall"] >= g["D2_fact_recall"]["min"],
            f"{m3.get('facts_used')}/{m3.get('facts_total')} facts used ({dims['D2_fact_recall']:.0%})")
    put("D3_precision", m2.get("unsupported_high", 0) <= g["D3_precision"]["max_unsupported_high"],
        f"{m2.get('unsupported_high', 0)} unsupported numbers/codes in factual text")
    put("D4_depth", dims["D4_depth"] >= g["D4_depth"]["min"] and (m3.get("floors_met") or not g["D4_depth"].get("floors_met")),
        f"checklist {m3.get('checklist_coverage', 0):.0%}; requirement floors {'met' if m3.get('floors_met') else 'not met'}")
    put("D5_req_quality", (dims["D5_req_quality"] or 0) >= g["D5_req_quality"]["min"], f"mean requirement score {dims['D5_req_quality']}")
    put("D6_specificity", (dims["D6_specificity"] or 0) >= g["D6_specificity"]["min"], f"specificity {dims['D6_specificity']}")
    put("D7_decisions", (dims["D7_decisions"] or 0) >= g["D7_decisions"]["min"], f"{dims['D7_decisions']:.0%} of decision sections pass")
    gc = g["D8_citations"]
    sr = m7.get("source_recall")
    put("D8_citations", m7.get("internal", 0) <= gc["max_internal"] and m7.get("unresolved", 0) <= gc["max_unresolved"]
        and (sr is None or sr >= gc["min_source_recall"]),
        f"{m7.get('internal', 0)} internal, {m7.get('unresolved', 0)} unresolved citations; key sources referenced "
        + (f"{sr:.0%}" if sr is not None else "n/a"))
    if fig_report is not None:
        put("D9_figures", fig_report.get("high", 0) <= g["D9_figures"]["max_high_defects"], f"{fig_report.get('high', 0)} high figure defects")
    if dims["D10_judge"] is not None:
        put("D10_judge", dims["D10_judge"] >= g["D10_judge"]["min"], f"P(as good as gold) {dims['D10_judge']}")
    return res


STORY_INDEPENDENT = ["D4_depth", "D5_req_quality", "D6_specificity", "D7_decisions"]


def overall(dims):
    vals = [v for v in dims.values() if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def relative(dims, gold_dims):
    a = [dims[k] for k in STORY_INDEPENDENT if dims.get(k) is not None and gold_dims.get(k) is not None]
    b = [gold_dims[k] for k in STORY_INDEPENDENT if dims.get(k) is not None and gold_dims.get(k) is not None]
    return round(min(1.0, sum(a) / sum(b)), 3) if a and sum(b) else None


# ------------------------------------------------------------------ J1 judge
def run_judge(doc_md, gold_md, max_chars=24000):
    if not slm.enabled("judge"):
        return None
    tmpl = JUDGE_PROMPT.read_text(encoding="utf-8")
    wins = total = 0
    detail = {}
    for dim, rubric in JUDGE_DIMENSIONS.items():
        votes = []
        for order in ("draft_first", "gold_first"):
            a, b = (doc_md, gold_md) if order == "draft_first" else (gold_md, doc_md)
            prompt = tmpl.replace("{DIMENSION}", dim).replace("{RUBRIC}", rubric) \
                .replace("{DOC_A}", a[:max_chars]).replace("{DOC_B}", b[:max_chars])
            try:
                v = slm.chat_json("Reply with JSON only.", prompt, profile="judge", max_tokens=300)
            except slm.SLMError as e:
                return {"error": str(e)}
            draft_score = v.get("a") if order == "draft_first" else v.get("b")
            gold_score = v.get("b") if order == "draft_first" else v.get("a")
            try:
                votes.append(float(draft_score) - float(gold_score))
            except (TypeError, ValueError):
                votes.append(0.0)
        # a win counts only when it holds in both orders
        both = 1.0 if all(x >= 0 for x in votes) else 0.0 if all(x < 0 for x in votes) else 0.5
        wins += both
        total += 1
        detail[dim] = {"delta_draft_minus_gold": votes, "credit": both}
    raw = wins / total if total else 0.0
    prob = raw
    if CALIBRATION.exists():
        c = json.loads(CALIBRATION.read_text(encoding="utf-8"))
        prob = 1 / (1 + math.exp(c["a"] * raw + c["b"]))
    return {"raw": round(raw, 3), "probability": round(prob, 3), "dimensions": detail}


# ------------------------------------------------------------------ main entry
def evaluate(ctx, fig_report=None, judge=False):
    findings, metrics = C.run_all(ctx)
    if fig_report:
        for name, v in fig_report.get("figures", {}).items():
            for d in v.get("defects", []):
                findings.append(ctx.finding("figure_qa", "C5", name, name, d["severity"], d["defect"], d["detail"],
                                            "Redraw: wrap long labels with \\n, widen boxes, route arrows in the gaps between boxes."))
    j = run_judge(ctx.doc.md, ctx.gold.md) if judge and ctx.gold else None
    dims = _norm(metrics, fig_report, j if j and "probability" in j else None)
    gates = gate_results(dims, metrics, fig_report)
    gold_dims = None
    if ctx.gold:
        gctx = C.Context(ctx.gold, ctx.facts, ctx.sources, ctx.story, ctx.evidence, ctx.source_pages, {}, gold=ctx.gold,
                         mode="rules")
        _, gm = C.run_all(gctx)
        gold_dims = _norm(gm)
    rel = relative(dims, gold_dims) if gold_dims else None
    hard_fail = [k for k, v in gates.items() if v["hard"] and not v["pass"]]
    rel_min = load_gates()["relative_to_gold"]["min"]
    passed = not hard_fail and (rel is None or rel >= rel_min)
    sev = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (sev.get(f["severity"], 3), f["critic"]))
    return {"dimensions": dims, "overall": overall(dims), "gold_dimensions": gold_dims, "relative_to_gold": rel,
            "gates": gates, "hard_failures": hard_fail, "pass": passed, "judge": j,
            "counts": {"findings": len(findings), "high": sum(f["severity"] == "high" for f in findings),
                       "medium": sum(f["severity"] == "medium" for f in findings),
                       "requirements": metrics["C1"]["requirements"], "words": ctx.doc.word_count()},
            "metrics": {k: {kk: vv for kk, vv in v.items() if kk not in ("scores",)} for k, v in metrics.items()}}, findings


def to_markdown(card, findings, title="Quality scorecard", limit=40):
    L = [f"# {title}", "",
         f"Gate: **{'PASS' if card['pass'] else 'FAIL'}**"
         + (f" · hard gates failed: {', '.join(card['hard_failures'])}" if card["hard_failures"] else "")
         + (f" · score vs gold {card['relative_to_gold']:.0%}" if card.get("relative_to_gold") is not None else ""), "",
         f"{card['counts']['words']} words · {card['counts']['requirements']} requirements · "
         f"{card['counts']['high']} high / {card['counts']['medium']} medium findings", "",
         "| Dimension | Score | Gold | Gate | Detail |", "|---|---|---|---|---|"]
    gd = card.get("gold_dimensions") or {}
    for k, v in card["dimensions"].items():
        g = card["gates"].get(k)
        gate = "–" if not g else ("pass" if g["pass"] else ("FAIL" if g["hard"] else "below target"))
        L.append(f"| {k} | {'–' if v is None else v} | {'–' if gd.get(k) is None else gd[k]} | {gate} | {g['why'] if g else ''} |")
    L += ["", "## Findings (most severe first)", "", "| # | Severity | Critic | Section | Target | Defect | Evidence | Fix |",
          "|---|---|---|---|---|---|---|---|"]
    for f in findings[:limit]:
        cell = lambda x: re.sub(r"\s+", " ", str(x)).replace("|", "/")[:160]  # noqa: E731
        L.append(f"| {f['finding_id']} | {f['severity']} | {f['critic']} | {cell(f['section'])} | {cell(f['target'])} | "
                 f"{f['defect']} | {cell(f['evidence'])} | {cell(f['suggestion'])} |")
    if len(findings) > limit:
        L.append(f"\n{len(findings) - limit} more findings in findings.jsonl.")
    return "\n".join(L) + "\n"
