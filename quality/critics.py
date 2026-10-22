"""
Critic panel. Each critic reads the draft and returns findings in one shared format:

    {"finding_id": "C1-0042", "critic": "req_quality", "section": "6. Rerun behavior", "target": "SRH-2",
     "severity": "high", "defect": "not_testable", "evidence": "...", "suggested_facts": ["F-017"],
     "suggestion": "..."}

Every critic runs on rules alone (deterministic, no model needed). When a small model is configured
(quality/slm.py) and mode="hybrid", C1 and C2 also ask it, and the two verdicts are combined.

  C1 req_quality   requirement rows: testable, specific, atomic, not vague, not duplicated, has a priority
  C2 claim_support numbers, versions and codes in the text must come from the findings, evidence, story or papers
  C3 coverage      section checklist (K2), requirement floors, fact recall against the ledger (K1), ask coverage
  C4 specificity   density of specifics per 100 words; vague sentences, with facts that would make them concrete
  C6 decision      DECISION sections: concrete options, pros/cons, stepwise recommendation, sign-off
  C7 citations     citations resolve to source papers and pages; no pipeline working files; key sources referenced
  C8 structure     figures placed in context and referenced, no standalone "Figures" section, no empty sections
(C5 figure QA lives in figure_qa.py because it has to run the figure script.)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from quality import facts as K1  # noqa: E402
from quality import patterns as K2  # noqa: E402
from quality import slm  # noqa: E402
from quality.doc_model import REQ_ID, Doc, words  # noqa: E402

VAGUE = ["appropriate", "adequate", "as needed", "as required", "etc", "robust", "efficient", "user-friendly",
         "flexible", "easy to", "clearly", "clear decision", "properly", "sufficient", "maintain versioning",
         "relevant", "various", "comprehensive", "seamless", "optimal", "best practice", "where applicable",
         "if necessary", "as appropriate", "and so on", "high quality", "state of the art", "in a timely manner"]
ABSOLUTE = r"\b(never|every|each|all|only|at least|at most|no more than|must not|cannot|within|before|after|per)\b"
HEDGE = r"to be confirmed|propos|target|illustrative|e\.g\.|for example|about |approximately|to be agreed|assum|starting point|tbc"
COMMON_ACRONYMS = {"ID", "IDS", "JSON", "CSV", "PDF", "API", "LLM", "AI", "OK", "US", "SME", "SMES", "QA", "ML", "URL",
                   "UTF", "HTML", "N", "Y", "TBD", "TBC", "IT", "UI", "KPI", "DECISION", "MUST", "SHOULD"}


class Context:
    def __init__(self, doc, facts=(), sources=(), story="", evidence="", source_pages=None, plan=None,
                 gold=None, inputs_text="", mode="rules", source_dir=None):
        self.doc = doc
        self.facts = list(facts)
        self.sources = list(sources)
        self.story = story
        self.evidence = evidence
        self.source_pages = source_pages or {}
        self.plan = plan or {}
        self.gold = gold
        self.inputs_text = inputs_text
        self.mode = mode if slm.enabled() else "rules"
        self.patterns = K2.load_patterns()
        self.source_dir = Path(source_dir) if source_dir else None
        self._n = 0

    def support_text(self):
        if not hasattr(self, "_support"):
            parts = [f["text"] for f in self.facts] + [self.story, self.evidence, self.inputs_text]
            parts += [t for pages in self.source_pages.values() for _, t in pages]
            self._support = "\n".join(parts)
            self._support_low = self._support.lower().replace(",", "")
        return self._support, self._support_low

    def finding(self, critic, prefix, section, target, severity, defect, evidence, suggestion="", facts=None):
        self._n += 1
        return {"finding_id": f"{prefix}-{self._n:04d}", "critic": critic, "section": section, "target": target,
                "severity": severity, "defect": defect, "evidence": evidence[:300],
                "suggested_facts": list(facts or []), "suggestion": suggestion}


def _jaccard(a, b):
    sa, sb = set(w.lower() for w in words(a) if len(w) > 3), set(w.lower() for w in words(b) if len(w) > 3)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def specifics(text):
    """Numbers, versions, codes and named standards: the things that make a sentence checkable."""
    t = re.sub(r"\*\*|\b[A-Z][A-Z0-9]{0,6}-\d+\b", "", text)   # ignore requirement IDs
    t = re.sub(r"\b(?:Section|Sections|Figure|Figures|Step|Table|Option|Q)\s*\d+(?:\s*(?:,|and|to|–|-)\s*\d+)*", "", t)
    t = re.sub(r"(?m)^\s*#*\s*\d+[.)]\s", "", t)
    nums = [n for n in re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?\s?%?", t) if not re.fullmatch(r"\d", n.strip())]
    codes = [c for c in re.findall(r"(?<![\w-])[A-Z][A-Z0-9]{1,6}(?:-[A-Z0-9]{1,4})?(?![\w-])", t) if c not in COMMON_ACRONYMS]
    names = re.findall(r"\b[A-Z][a-z]+[A-Z][A-Za-z]+\b|\bv\d+(?:\.\d+)+\b", t)
    return nums + codes + names


# ====================================================================== C1
def score_requirement(text, priority):
    defects, score = [], 1.0
    low = text.lower()
    n = len(words(text))
    vague = [v for v in VAGUE if re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", low)]
    if vague:
        defects.append(("vague", f"vague wording: {', '.join(vague[:3])}"))
        score -= min(0.5, 0.25 * len(vague))
    measurable = bool(specifics(text)) or len(re.findall(r",", text)) >= 2 or re.search(ABSOLUTE, low) \
        or re.search(r":\s*\S", text) and n >= 12
    if not measurable:
        defects.append(("not_testable", "no measurable condition, enumeration, number or named artifact"))
        score -= 0.4
    if n < 6:
        defects.append(("too_short", f"only {n} words"))
        score -= 0.2
    if n > 110:
        defects.append(("not_atomic", f"{n} words – probably several requirements in one row"))
        score -= 0.15
    if re.search(r"research_evidence\.md|research_findings\.md|research findings,? section|\bQ\d\]", text, re.I):
        defects.append(("internal_citation", "cites a pipeline working file instead of a source"))
        score -= 0.3
    if priority.strip().lower() not in ("must", "should", "could", "won't", "may"):
        defects.append(("no_priority", "priority is not Must/Should"))
        score -= 0.1
    return max(0.0, round(score, 2)), defects


C1_SYSTEM = ("You review requirements in a requirements document. Score the requirement from 0 to 1 for: testable "
             "(a reviewer can check it passed), specific (named artifacts, numbers or rules), atomic (one requirement), "
             "unambiguous. Reply as JSON: {\"score\": 0.0-1.0, \"defects\": [\"not_testable\"|\"vague\"|\"not_atomic\"|"
             "\"ambiguous\"], \"reason\": \"one sentence\", \"rewrite_hint\": \"one sentence\"}")


def c1_requirements(ctx):
    out, scores = [], {}
    reqs = ctx.doc.requirements
    for i, r in enumerate(reqs):
        s, defects = score_requirement(r["text"], r["priority"])
        hint = ""
        if ctx.mode == "hybrid":
            try:
                v = slm.chat_json(C1_SYSTEM, f"Section: {r['section']}\nRequirement {r['id']}: {r['text']}")
                s = round(0.5 * s + 0.5 * float(v.get("score", s)), 2)
                for d in v.get("defects", []):
                    if d not in [x[0] for x in defects]:
                        defects.append((d, v.get("reason", "")))
                hint = v.get("rewrite_hint", "")
            except (slm.SLMError, ValueError, TypeError):
                pass
        for j in range(i):
            if _jaccard(r["text"], reqs[j]["text"]) >= 0.6:
                defects.append(("duplicate", f"near-duplicate of {reqs[j]['id']}"))
                s = max(0.0, s - 0.3)
                break
        scores[r["id"]] = s
        for d, ev in defects:
            sev = "high" if d in ("not_testable", "internal_citation") or s < 0.5 else "medium" if d != "no_priority" else "low"
            sug = {"vague": "Replace the vague words with the rule, number or artifact a reviewer can check.",
                   "not_testable": "State the condition that proves it is met (a number, a named file, an enumerated list, never/every).",
                   "too_short": "Add the rule behind the heading word.",
                   "not_atomic": "Split into separate requirements with their own IDs.",
                   "internal_citation": "Cite the source paper [file, p.N] or the reference, not the pipeline's working files.",
                   "duplicate": "Merge with the earlier requirement or make the difference explicit.",
                   "no_priority": "Set Must or Should."}.get(d, hint or "Rewrite to be testable and specific.")
            out.append(ctx.finding("req_quality", "C1", r["section"], r["id"], sev, d, f"{r['id']}: {ev}", sug))
    return out, {"requirements": len(reqs), "mean_score": round(sum(scores.values()) / len(scores), 3) if scores else 0.0,
                 "share_not_testable": round(sum(1 for f in out if f["defect"] == "not_testable") / len(reqs), 3) if reqs else 1.0,
                 "scores": scores}


# ====================================================================== C2
C2_SYSTEM = ("You check whether a claim is supported by the evidence passages. Reply as JSON: {\"verdict\": "
             "\"supported\"|\"unsupported\"|\"contradicted\", \"reason\": \"one sentence\"}. Use only the passages.")


def c2_claims(ctx):
    out = []
    support, support_low = ctx.support_text()
    id_prefixes = {r["id"].split("-")[0] for r in ctx.doc.requirements}
    checked = unsupported = 0
    for s in ctx.doc.sections:
        if re.search(r"reference|open items", s.heading, re.I):
            continue
        sec_hedged = bool(re.search(r"propos|target|illustrative|to be confirmed", s.heading + " " + s.text[:400], re.I))
        req_lines = {ln for ln in s.raw_lines if re.match(r"^\|\s*\**[A-Z][A-Z0-9]{0,6}-\d+", ln.strip())}
        ask_table = False
        for ln in s.raw_lines:
            st = ln.strip()
            if re.match(r"^\|\s*ask\s*\|", st, re.I):
                ask_table = True
            elif not st.startswith("|"):
                ask_table = False
            if not st or ask_table or st.startswith("![") or re.match(r"^\|?\s*-{3}", st):
                continue
            clean = re.sub(r"\*\*|\b[A-Z][A-Z0-9]{0,6}-\d+\b|\b(?:Section|Sections|Figure|Figures|Step|Level|Tier|Stage|Phase|Option|Table|Issue)\s+\d+(?:\s*(?:,|and|to|–|-)\s*\d+)*",
                           " ", ln)
            clean = re.sub(r"^\|\s*\d+\s", "| ", clean)                       # numbered stage cells
            clean = re.sub(r"(?m)^\s*\d+[.)]\s", "", clean)
            nums = re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?\s?%?", clean)
            codes = [c for c in re.findall(r"(?<![\w-])[A-Z][A-Z0-9]{1,6}(?:-[A-Z0-9]{1,4})?(?![\w-])", clean)
                     if c not in COMMON_ACRONYMS and c not in id_prefixes]
            hedged = sec_hedged or re.search(HEDGE, ln, re.I)
            for tok in dict.fromkeys(nums + codes):
                t = tok.replace(" ", "")
                if re.fullmatch(r"[1-9]", t):          # small counts are structure, not claims
                    continue
                checked += 1
                tl = t.lower().replace(",", "")
                ok = (re.search(r"(?<![\d.])" + re.escape(tl) + r"(?![\d])", support_low) if re.match(r"\d", tl)
                      else re.search(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", support))
                if ok:
                    continue
                unsupported += 1
                if ln in req_lines:
                    sev, defect = "low", "design_value_unconfirmed"
                    sug = "A design value, not a sourced fact: mark it 'proposed' or 'to be confirmed' if the team has not agreed it."
                elif hedged:
                    continue
                else:
                    in_table = ln.strip().startswith("|")
                    sev = "high" if re.match(r"\d", t) and not in_table else "medium"
                    defect = "unsupported_claim"
                    sug = "Use the value from the findings or a source paper, or mark it 'to be confirmed'."
                out.append(ctx.finding("claim_support", "C2", s.heading, t, sev, defect,
                                       f"'{t}' is not in the findings, evidence, story or source papers: {ln.strip()[:160]}", sug))
    # optional model check of prose sentences carrying specifics
    if ctx.mode == "hybrid" and ctx.facts:
        for s in ctx.doc.sections:
            for b in s.blocks:
                if b["type"] != "paragraph":
                    continue
                for sent in re.split(r"(?<=[.!?])\s+", b["text"]):
                    if len(specifics(sent)) < 2 or re.search(HEDGE, sent, re.I):
                        continue
                    top = sorted(ctx.facts, key=lambda f: -_jaccard(sent, f["text"]))[:4]
                    try:
                        v = slm.chat_json(C2_SYSTEM, "Passages:\n" + "\n".join(f"- {f['text']}" for f in top) + f"\n\nClaim: {sent}")
                    except slm.SLMError:
                        continue
                    if v.get("verdict") in ("unsupported", "contradicted"):
                        out.append(ctx.finding("claim_support", "C2", s.heading, sent[:60],
                                               "high" if v["verdict"] == "contradicted" else "medium",
                                               v["verdict"] + "_claim", v.get("reason", ""),
                                               "Correct the claim from the findings or mark it 'to be confirmed'.",
                                               [f["id"] for f in top[:2]]))
    high = sum(1 for f in out if f["severity"] == "high")
    return out, {"claims_checked": checked, "unsupported": unsupported, "unsupported_high": high,
                 "precision": round(1 - high / checked, 3) if checked else 1.0}


# ====================================================================== C3
def _plan_sections(plan):
    return {re.sub(r"\s+", " ", s.get("heading", "")).strip().lower(): s for s in plan.get("sections", [])}


def c3_coverage(ctx):
    out = []
    pats = ctx.patterns["types"]
    per_section, cov_vals, floors_ok = [], [], True
    plan_secs = _plan_sections(ctx.plan)
    for s in ctx.doc.sections:
        types = K2.classify(s.heading, ctx.patterns)
        ps = plan_secs.get(s.heading.strip().lower())
        if ps and ps.get("type") in pats and ps["type"] not in types:
            types = [ps["type"]]
        row = {"section": s.heading, "types": types, "requirements": len(s.requirements), "words": s.word_count()}
        if not types:
            per_section.append(row)
            continue
        hits_all, miss_all, floor = [], [], 0
        for t in types:
            hits, misses = K2.topic_hits(s.text, t, ctx.patterns)
            hits_all += [h["label"] for h in hits]
            miss_all += [m["label"] for m in misses]
            floor += pats[t].get("min_requirements", 0)
            mtr = pats[t].get("min_table_rows")
            if mtr:
                rows = max((len(tb["rows"]) for tb in s.tables), default=0)
                if rows < mtr:
                    out.append(ctx.finding("coverage", "C3", s.heading, t, "medium", "thin_table",
                                           f"largest table has {rows} rows; a {t} section needs at least {mtr}",
                                           "Add rows until the table covers: " + "; ".join(x["label"] for x in pats[t]["topics"][:4])))
            mref = pats[t].get("min_references")
            if mref and len(ctx.doc.references()) < mref:
                out.append(ctx.finding("coverage", "C3", s.heading, t, "high", "few_references",
                                       f"{len(ctx.doc.references())} references; need at least {mref}",
                                       "List every source paper and key source cited, with links."))
            mw = pats[t].get("min_words")
            if mw and s.word_count() < mw:
                out.append(ctx.finding("coverage", "C3", s.heading, t, "medium", "thin_section",
                                       f"{s.word_count()} words; a {t} section needs about {mw}",
                                       "Say what the system does, who decides, where the result goes and what this document asks the team to decide."))
        cov = len(hits_all) / (len(hits_all) + len(miss_all)) if hits_all or miss_all else 1.0
        cov_vals.append(cov)
        row.update({"checklist_coverage": round(cov, 2), "floor": floor, "missing_topics": miss_all})
        per_section.append(row)
        if len(types) > 1:
            out.append(ctx.finding("coverage", "C3", s.heading, "+".join(types), "high", "merged_sections",
                                   f"one section covers {', '.join(types)}",
                                   "Give each topic its own numbered section with its own requirement table."))
        if floor and len(s.requirements) < floor:
            floors_ok = False
            out.append(ctx.finding("coverage", "C3", s.heading, "requirements", "high", "below_requirement_floor",
                                   f"{len(s.requirements)} requirements; this section type needs at least {floor}",
                                   "Add requirements for the missing checklist topics: " + "; ".join(miss_all[:5])))
        if miss_all and cov < 0.7:
            out.append(ctx.finding("coverage", "C3", s.heading, "checklist", "high" if cov < 0.5 else "medium",
                                   "missing_topics", f"covers {cov:.0%} of the checklist",
                                   "Cover: " + "; ".join(miss_all[:6])))
    # fact recall against the ledger
    rec, used, missing = K1.recall(ctx.facts, ctx.doc.text, common_text=ctx.story) if ctx.facts else (None, [], [])
    if ctx.facts:
        assigned = {}
        for sec in ctx.plan.get("sections", []):
            for fid in sec.get("facts", []):
                assigned[fid] = sec.get("heading", "")
        unused_ok = {u.get("id") for u in ctx.plan.get("unused_facts", [])}
        by_id = {f["id"]: f for f in ctx.facts}
        for fid in missing:
            if fid in unused_ok:
                continue
            f = by_id[fid]
            sec = assigned.get(fid) or "(not assigned)"
            out.append(ctx.finding("coverage", "C3", sec, fid, "medium", "fact_not_used",
                                   f"{fid}: {f['text'][:200]}", "Use this fact where it applies (keep its numbers, codes and caveats).", [fid]))
    # ask coverage
    asks = ctx.plan.get("asks", [])
    ask_ok = ask_total = 0
    nums = {s.number for s in ctx.doc.sections if s.word_count() >= 40 or s.requirements or s.tables}
    if asks:
        for a in asks:
            ask_total += 1
            n = str(a.get("section", "")).split(" ", 1)[0].rstrip(".")
            if n.isdigit() and int(n) in nums or "figure" in a.get("section", "").lower():
                ask_ok += 1
            else:
                out.append(ctx.finding("coverage", "C3", a.get("section", ""), "ask", "high", "ask_not_covered",
                                       a.get("ask", "")[:200], "Cover this ask with requirements or a decision in its own section."))
    else:
        t = ctx.doc.ask_table()
        if t:
            for r in t["rows"]:
                ask_total += 1
                refs = [int(x) for x in re.findall(r"\b(\d{1,2})\b", r[1])] if len(r) > 1 else []
                if "figure" in r[1].lower() or (refs and all(x in nums for x in refs)):
                    ask_ok += 1
                else:
                    out.append(ctx.finding("coverage", "C3", r[1] if len(r) > 1 else "", "ask", "high", "ask_not_covered",
                                           r[0][:200], "Cover this ask in the section the table names."))
        else:
            out.append(ctx.finding("coverage", "C3", "1. Summary", "ask_table", "high", "no_ask_table",
                                   "no 'Ask | Section' table", "Add the ask-to-section table to the summary."))
    return out, {"sections": per_section, "checklist_coverage": round(sum(cov_vals) / len(cov_vals), 3) if cov_vals else 0.0,
                 "floors_met": floors_ok, "fact_recall": round(rec, 3) if rec is not None else None,
                 "facts_used": len(used), "facts_total": len(used) + len(missing),
                 "ask_coverage": round(ask_ok / ask_total, 3) if ask_total else 0.0}


# ====================================================================== C4
def density(doc):
    w = doc.word_count()
    return round(100 * len(specifics(doc.plain_text())) / w, 2) if w else 0.0


def c4_specificity(ctx):
    out = []
    vague_n = 0
    for s in ctx.doc.sections:
        if re.search(r"reference", s.heading, re.I):
            continue
        for b in s.blocks:
            texts = [b["text"]] if b["type"] == "paragraph" else b.get("items", []) if b["type"] == "bullets" else \
                [c for r in b.get("rows", []) for c in r[1:]] if b["type"] == "table" else []
            for t in texts:
                for sent in re.split(r"(?<=[.!?;])\s+", t):
                    if len(words(sent)) < 8 or specifics(sent):
                        continue
                    hits = [v for v in VAGUE if re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", sent.lower())]
                    generic = re.search(r"\b(ensure|support|enable|handle|manage|maintain|provide|align|balance|aligns?)\b", sent, re.I)
                    if hits or generic:
                        vague_n += 1
                        sug_facts = [f["id"] for f in sorted(ctx.facts, key=lambda f: -_jaccard(sent, f["text"]))[:2]
                                     if _jaccard(sent, f["text"]) > 0.08]
                        out.append(ctx.finding("specificity", "C4", s.heading, sent[:50], "medium", "vague_sentence",
                                               sent[:220], "Make it concrete: name the rule, number, code or artifact.", sug_facts))
    d = density(ctx.doc)
    gd = density(ctx.gold) if ctx.gold else None
    if gd and d < 0.8 * gd:
        out.append(ctx.finding("specificity", "C4", "(whole document)", "density", "high", "low_density",
                               f"{d} specifics per 100 words vs {gd} in the gold document",
                               "Bring in the numbers, versions, codes and named methods from the fact ledger."))
    return out, {"density": d, "gold_density": gd, "vague_sentences": vague_n,
                 "relative_density": round(min(1.0, d / gd), 3) if gd else None}


# ====================================================================== C6
def c6_decisions(ctx):
    out, results = [], []
    decs = [s for s in ctx.doc.sections if s.is_decision]
    story_open = bool(re.search(r"open question|\?\s*$", ctx.story, re.I | re.M))
    if story_open and not decs:
        out.append(ctx.finding("decision", "C6", "(whole document)", "decision", "high", "no_decision_section",
                               "the story has an open question but no section is marked (DECISION)",
                               "Add a (DECISION) section for each open question."))
    has_signoff = bool(re.search(r"\|\s*agree\?", ctx.doc.text, re.I))
    for s in decs:
        problems = []
        opt = next((t for t in s.tables if t["columns"] and re.match(r"option|proposal|choice", t["columns"][0], re.I)), None)
        if not opt:
            problems.append(("no_options_table", "no Option | Pros | Cons (or Proposal) table"))
        else:
            cols = [c.lower() for c in opt["columns"]]
            if len(opt["rows"]) < 3:
                problems.append(("too_few_options", f"{len(opt['rows'])} options; give at least 3 (include a hybrid or phased option)"))
            cells = [c for r in opt["rows"] for c in r[1:]]
            avg = sum(len(words(c)) for c in cells) / len(cells) if cells else 0
            if avg < 10:
                problems.append(("thin_options", f"option cells average {avg:.0f} words; give the concrete members, effects and costs"))
            if not any(specifics(" ".join(r)) for r in opt["rows"]):
                problems.append(("abstract_options", "options name no concrete codes, items or numbers"))
            if not ("pros" in cols and "cons" in cols) and not any(re.search(r"why|codes|members", c) for c in cols):
                problems.append(("no_pros_cons", "options table has no Pros/Cons or rationale column"))
        rec_text = ""
        m = re.search(r"(?im)^(##\s*recommend.*|recommend.*)$", s.text)
        if m:
            rec_text = s.text[m.start():]
        elif opt and any("recommend" in " ".join(r).lower() for r in opt["rows"]):
            rec_text = " ".join(" ".join(r) for r in opt["rows"] if "recommend" in " ".join(r).lower())
        if not rec_text and opt and re.match(r"proposal", opt["columns"][0], re.I) and re.search(r"propos", s.text, re.I):
            rec_text = s.text            # a 'Proposal' table is itself the recommendation
        rec_words = len(words(rec_text))
        steps = len(re.findall(r"(?m)^\s*(?:[-*]|\d+[.)])\s+", rec_text))
        if not rec_text:
            problems.append(("no_recommendation", "no recommendation"))
        elif rec_words < 40 and steps < 2:
            problems.append(("thin_recommendation", f"recommendation is {rec_words} words with {steps} steps; say how, in order, with the stopping rule or criteria"))
        if not re.search(r"\|\s*agree\?|questions for the team", s.text, re.I) and not has_signoff:
            problems.append(("no_signoff", "no questions for the team or sign-off table"))
        for d, ev in problems:
            out.append(ctx.finding("decision", "C6", s.heading, "decision", "high" if d in
                                   ("no_options_table", "no_recommendation", "abstract_options", "too_few_options") else "medium",
                                   d, ev, "Match the gold decision sections: concrete options with pros and cons, a stepwise "
                                   "recommendation, questions for the team and a sign-off table."))
        results.append({"section": s.heading, "pass": not any(p[0] in ("no_options_table", "no_recommendation", "abstract_options",
                                                                       "too_few_options", "thin_recommendation", "thin_options")
                                                              for p in problems), "problems": [p[0] for p in problems]})
    rate = sum(r["pass"] for r in results) / len(results) if results else (0.0 if story_open else 1.0)
    return out, {"decisions": results, "pass_rate": round(rate, 3)}


# ====================================================================== C7
def c7_citations(ctx):
    out = []
    internal = ctx.patterns.get("internal_files", [])
    cites = ctx.doc.citations()
    resolved = bad = 0
    names = {n.lower(): n for n in ctx.source_pages} | ({p.name.lower(): p.name for p in ctx.source_dir.glob("*")}
                                                        if ctx.source_dir and ctx.source_dir.exists() else {})
    for f, page, raw in cites:
        fl = f.lower().strip()
        if any(i.lower() in fl for i in internal):
            bad += 1
            out.append(ctx.finding("citations", "C7", "", raw, "high", "internal_citation", raw,
                                   "Cite the source paper and page, or the reference entry, not a pipeline working file."))
            continue
        if names and fl not in names:
            bad += 1
            out.append(ctx.finding("citations", "C7", "", raw, "high", "unresolved_citation", f"{f} is not in research/sources",
                                   "Use the exact file name from research/sources."))
            continue
        if page and names.get(fl) in ctx.source_pages:
            pages = dict(ctx.source_pages[names[fl]])
            if page not in pages:
                bad += 1
                out.append(ctx.finding("citations", "C7", "", raw, "high", "bad_page", f"{f} has no page {page}",
                                       "Check the page number in research/sources/_text."))
                continue
        resolved += 1
    for pat in [r"\(research findings,? section \d+\)", r"research_evidence\.md", r"stories/\d+/"]:
        for m in re.finditer(pat, ctx.doc.text, re.I):
            out.append(ctx.finding("citations", "C7", "", m.group(0), "high", "internal_citation", m.group(0),
                                   "Cite the underlying source (paper, standard or URL) instead of the findings file."))
    refs = ctx.doc.references()
    ref_text = "\n".join(refs)
    for r in refs:
        if any(i.lower() in r.lower() for i in internal):
            out.append(ctx.finding("citations", "C7", "References", r[:60], "high", "internal_reference", r[:200],
                                   "References list the sources behind the findings, not the pipeline's files."))
    srec, smiss = K1.source_recall(ctx.sources, ref_text) if ctx.sources else (None, [])
    for t in smiss:
        out.append(ctx.finding("citations", "C7", "References", t[:60], "medium", "key_source_missing", t,
                               "Add this key source from the findings to References."))
    internal_n = sum(1 for f in out if f["defect"] in ("internal_citation", "internal_reference"))
    return out, {"citations": len(cites), "resolved": resolved, "unresolved": bad, "internal": internal_n,
                 "references": len(refs), "source_recall": round(srec, 3) if srec is not None else None}


# ====================================================================== C8
def c8_structure(ctx):
    out = []
    figs = ctx.doc.figures
    for s in ctx.doc.sections:
        if re.fullmatch(r"\d+[.)]?\s*(figures?|visuals?|diagrams?)", s.heading.strip(), re.I):
            out.append(ctx.finding("structure", "C8", s.heading, "figures", "high", "standalone_figures_section",
                                   "figures are collected in their own section",
                                   "Place each figure beside the section it explains and delete this section."))
        if not s.blocks and not s.text.strip():
            out.append(ctx.finding("structure", "C8", s.heading, "empty", "high", "empty_section", "section has no content", "Fill or remove it."))
    body_wo_caps = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", ctx.doc.text)
    for i, f in enumerate(figs, 1):
        if not re.search(rf"\bFigures?\s+(?:\d+\s*(?:,|and)\s*)*{i}\b", body_wo_caps):
            out.append(ctx.finding("structure", "C8", "", f["file"], "medium", "figure_not_referenced",
                                   f"Figure {i} ({f['file']}) is never referred to in the text",
                                   f"Refer to Figure {i} where its content is discussed."))
    return out, {"figures": len(figs)}


CRITICS = [("C1", c1_requirements), ("C2", c2_claims), ("C3", c3_coverage), ("C4", c4_specificity),
           ("C6", c6_decisions), ("C7", c7_citations), ("C8", c8_structure)]


def run_all(ctx):
    findings, metrics = [], {}
    for name, fn in CRITICS:
        f, m = fn(ctx)
        findings += f
        metrics[name] = m
    return findings, metrics


# ====================================================================== context from a story folder
def load_source_pages(src_dir):
    """{file name: [(page, text)]} from research/sources/_text, extracting any file that has no cache yet."""
    pages = {}
    src_dir = Path(src_dir)
    if src_dir.exists():
        import research_findings as RF
        for f in sorted(src_dir.iterdir()):
            if f.suffix.lower() not in (".pdf", ".html", ".htm", ".txt") or f.name.endswith("_NOT_A_PDF.html"):
                continue
            cache = src_dir / "_text" / (f.name + ".json")
            if not cache.exists():
                cache.parent.mkdir(exist_ok=True)
                try:
                    import logging
                    logging.getLogger("pypdf").setLevel(logging.CRITICAL)
                    data = RF.read_pages(f)
                except Exception:  # noqa: BLE001  – damaged file: cache it as empty so it is not retried
                    data = []
                cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tdir = Path(src_dir) / "_text"
    if tdir.exists():
        for j in tdir.glob("*.json"):
            try:
                data = json.loads(j.read_text(encoding="utf-8"))
                name = j.stem
                pages[name] = [(int(p), t) for p, t in data] if isinstance(data, list) else []
            except Exception:  # noqa: BLE001
                continue
    return pages


def context_for_story(story_dir, content_path=None, gold_path=None, mode="rules"):
    from quality.doc_model import load
    d = Path(story_dir)
    doc = load(content_path or d / "content.md")
    if not (d / "facts.jsonl").exists() and (d / "research_findings.md").exists():
        f, s = K1.build((d / "research_findings.md").read_text(encoding="utf-8"))
        K1.write(f, s, d)
    facts, sources = K1.load(d)
    plan = json.loads((d / "plan.json").read_text(encoding="utf-8")) if (d / "plan.json").exists() else {}
    ev = (d / "research" / "research_evidence.md")
    inputs = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in (d / "inputs" / "_text").glob("*.txt")) \
        if (d / "inputs" / "_text").exists() else ""
    gold = load(gold_path) if gold_path and Path(gold_path).exists() else None
    return Context(doc, facts, sources, story=(d / "story.md").read_text(encoding="utf-8") if (d / "story.md").exists() else "",
                   evidence=ev.read_text(encoding="utf-8") if ev.exists() else "",
                   source_pages=load_source_pages(d / "research" / "sources"), plan=plan, gold=gold,
                   inputs_text=inputs, mode=mode, source_dir=d / "research" / "sources")
