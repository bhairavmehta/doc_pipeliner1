"""
K2 – section-pattern library.

section_patterns.json (curated) says what each section type must cover; exemplars.json (mined from gold
documents) holds real requirement rows and decision tables to show the writer.

    python quality/patterns.py mine                      # mine examples/gold/**/*.md into exemplars.json
    python quality/patterns.py mine --gold path/to/gold  # another gold folder
    python quality/patterns.py show rerun                # print the checklist + exemplars for one type
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
PATTERNS = HERE / "patterns" / "section_patterns.json"
EXEMPLARS = HERE / "patterns" / "exemplars.json"
GOLD = HERE.parent / "examples" / "gold"

_ORDER = ["decision", "references", "open_items", "summary", "at_a_glance", "validation", "inputs", "outputs",
          "rerun", "review_handoff", "source_handling", "method", "governance"]


def load_patterns():
    return json.loads(PATTERNS.read_text(encoding="utf-8"))


def load_exemplars():
    return json.loads(EXEMPLARS.read_text(encoding="utf-8")) if EXEMPLARS.exists() else {}


def classify(heading, patterns=None):
    """Section types a heading belongs to (a merged section such as 'Sources, reruns and handoff' gets several)."""
    pats = (patterns or load_patterns())["types"]
    h = re.sub(r"^\d+[.)]?\s*", "", heading.lower())
    found = []
    for t in _ORDER:
        if t not in pats:
            continue
        for kw in pats[t]["match"]:
            if kw.lower() in h:
                found.append(t)
                break
    if "decision" in found:
        return ["decision"]
    if "references" in found:
        return ["references"]
    if "open_items" in found:
        return ["open_items"]
    if "review_handoff" in found and "source_handling" not in found and "rerun" not in found and "validation" in found:
        found.remove("review_handoff")
    return found


def topic_hits(text, ptype, patterns=None):
    pats = (patterns or load_patterns())["types"][ptype]
    hits, misses = [], []
    for tp in pats["topics"]:
        ok = any(re.search(kw, text, re.I) for kw in tp["keywords"])
        (hits if ok else misses).append(tp)
    return hits, misses


def brief(ptype, n_exemplars=3, patterns=None, exemplars=None):
    """Markdown brief for one section type: floor, checklist and gold exemplar rows."""
    pats = (patterns or load_patterns())["types"].get(ptype)
    if not pats:
        return ""
    ex = (exemplars if exemplars is not None else load_exemplars()).get(ptype, [])
    lines = [f"Section type: {ptype}"]
    if pats.get("min_requirements"):
        lines.append(f"At least {pats['min_requirements']} requirements (ID | Requirement | Priority).")
    if pats.get("min_table_rows"):
        lines.append(f"A table with at least {pats['min_table_rows']} rows, each with a measurable target.")
    if pats.get("min_references"):
        lines.append(f"At least {pats['min_references']} references with links; never cite pipeline working files.")
    lines.append("Must cover:")
    lines += [f"- {t['label']}" for t in pats["topics"]]
    if ex:
        lines.append("Gold exemplar rows (match this depth and specificity; do not copy content that does not apply):")
        lines += [f"- {e}" for e in ex[:n_exemplars]]
    return "\n".join(lines)


def mine(gold_dir=GOLD, per_type=6):
    from quality.doc_model import load
    pats = load_patterns()
    out = {}
    for f in sorted(Path(gold_dir).rglob("*.md")):
        doc = load(f)
        for s in doc.sections:
            for t in classify(s.heading, pats):
                if t in ("summary", "open_items", "references"):
                    continue
                rows = out.setdefault(t, [])
                if t == "decision":
                    for tb in s.tables:
                        if tb["columns"] and tb["columns"][0].lower().startswith("option"):
                            for r in tb["rows"]:
                                rows.append(" | ".join(r))
                    continue
                for r in s.requirements:
                    rows.append(f"{r['id']} | {r['text']} | {r['priority']}")
                if not s.requirements:
                    for tb in s.tables:
                        for r in tb["rows"]:
                            if any(c.strip() for c in r[1:]):
                                rows.append(" | ".join(r))
    # keep the most specific rows: those with numbers, codes or enumerations
    def spec(r):
        return len(re.findall(r"\d|[A-Z]{2,}|,|:", r)) + min(len(r) / 80, 2)
    out = {t: sorted(dict.fromkeys(v), key=spec, reverse=True)[:per_type] for t, v in out.items()}
    EXEMPLARS.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mine")
    m.add_argument("--gold", default=str(GOLD))
    s = sub.add_parser("show")
    s.add_argument("type")
    a = ap.parse_args()
    if a.cmd == "mine":
        out = mine(a.gold)
        print(f"Wrote {EXEMPLARS.name}: " + ", ".join(f"{k} {len(v)}" for k, v in out.items()))
    else:
        print(brief(a.type, n_exemplars=10))


if __name__ == "__main__":
    main()
