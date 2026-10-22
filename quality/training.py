"""
Feedback flywheel: export training data for the small-model critics.

Sources it reads
  examples/gold/**/*.md           approved gold documents (positive examples)
  stories/*/content.generated.md  what the pipeline produced (saved automatically by the critique step)
  stories/*/content.md            the same document after people edited it (if they did)
  stories/*/findings.jsonl        critic findings for the generated draft (weak labels)

What it writes (training/)
  c1_requirements.jsonl   requirement rows with a label (1 = good, 0 = defective) and defect tags      -> C1
  c4_sentences.jsonl      sentences labelled specific / vague                                           -> C4
  preference_pairs.jsonl  {prompt, chosen, rejected} per section: human-edited vs generated            -> DPO / reward model (C1, C4, J1)
  sft_c1_chat.jsonl       the C1 data as chat examples for supervised fine-tuning of an SLM (QLoRA)

Synthetic negatives are made from gold rows by removing numbers, replacing specifics with vague words,
truncating to the heading word, and merging two rows.

    python quality/training.py export                 # all stories + gold
    python quality/training.py export --out training --no-synthetic
    python quality/training.py stats
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from quality import critics as C  # noqa: E402
from quality.doc_model import load, words  # noqa: E402

C1_SYSTEM = C.C1_SYSTEM
VAGUE_SWAPS = ["as needed", "in an appropriate way", "efficiently", "with clear decision points", "as required",
               "in a robust manner"]


def _rows(doc):
    return [(r["section"], r["id"], r["text"], r["priority"]) for r in doc.requirements]


def degrade(text, rnd):
    """Return (bad_text, defect) – a plausible weak version of a good requirement."""
    choice = rnd.choice(["strip_specifics", "vague", "truncate"])
    if choice == "strip_specifics":
        t = re.sub(r"\b\d+(?:[.,]\d+)?\s?%?|\bv\d+(?:\.\d+)+|\b[A-Z]{2,}(?:-[A-Z0-9]+)?\b", "", text)
        t = re.sub(r"\s{2,}", " ", re.sub(r"\(\s*\)|,\s*,", "", t)).strip()
        return t, "not_specific"
    if choice == "vague":
        head = re.split(r"[.:]", text)[0]
        return f"{head}: handle this {rnd.choice(VAGUE_SWAPS)}.", "vague"
    return re.split(r"[.:]", text)[0].strip() + ".", "not_testable"


def export(out_dir, synthetic=True, seed=7):
    rnd = random.Random(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    c1, c4, prefs = [], [], []
    gold_files = sorted((ROOT / "examples" / "gold").rglob("*.md"))
    for g in gold_files:
        doc = load(g)
        rows = _rows(doc)
        for sec, rid, text, pr in rows:
            c1.append({"text": text, "section": sec, "label": 1, "defects": [], "source": f"gold:{g.name}:{rid}"})
            if synthetic:
                bad, defect = degrade(text, rnd)
                if bad and bad != text:
                    c1.append({"text": bad, "section": sec, "label": 0, "defects": [defect], "source": f"synthetic:{g.name}:{rid}"})
                    prefs.append({"prompt": f"Write requirement {rid} for section '{sec}'.", "chosen": text, "rejected": bad,
                                  "source": f"synthetic:{g.name}:{rid}"})
        if synthetic and len(rows) > 3:
            for _ in range(max(1, len(rows) // 6)):
                a, b = rnd.sample(rows, 2)
                c1.append({"text": a[2] + " Also, " + b[2][0].lower() + b[2][1:], "section": a[0], "label": 0,
                           "defects": ["not_atomic"], "source": f"synthetic-merge:{g.name}:{a[1]}+{b[1]}"})
        for s in doc.sections:
            for b in s.blocks:
                if b["type"] == "paragraph":
                    for sent in re.split(r"(?<=[.!?])\s+", b["text"]):
                        if len(words(sent)) >= 8:
                            c4.append({"text": sent, "label": 1 if C.specifics(sent) else 0, "source": f"gold:{g.name}"})
    for d in sorted((ROOT / "stories").glob("*")) if (ROOT / "stories").exists() else []:
        gen, final = d / "content.generated.md", d / "content.md"
        if not gen.exists():
            continue
        gdoc = load(gen)
        findings = [json.loads(l) for l in (d / "findings.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()] \
            if (d / "findings.jsonl").exists() else []
        defects = {}
        for f in findings:
            if f["critic"] == "req_quality":
                defects.setdefault(f["target"], []).append(f["defect"])
        for sec, rid, text, pr in _rows(gdoc):
            s, _ = C.score_requirement(text, pr)
            c1.append({"text": text, "section": sec, "label": 1 if s >= 0.8 and not defects.get(rid) else 0,
                       "defects": defects.get(rid, []), "source": f"draft:{d.name}:{rid}", "weak_label": True})
        if final.exists() and final.read_text(encoding="utf-8") != gen.read_text(encoding="utf-8"):
            fdoc = load(final)
            frows = {rid: text for _, rid, text, _ in _rows(fdoc)}
            for sec, rid, text, pr in _rows(gdoc):
                if rid in frows and frows[rid].strip() != text.strip():
                    prefs.append({"prompt": f"Write requirement {rid} for section '{sec}'.", "chosen": frows[rid],
                                  "rejected": text, "source": f"human-edit:{d.name}:{rid}"})
                    c1.append({"text": frows[rid], "section": sec, "label": 1, "defects": [], "source": f"human:{d.name}:{rid}"})
            gsec = {s.heading: s.text for s in gdoc.sections}
            for s in fdoc.sections:
                if s.heading in gsec and gsec[s.heading].strip() != s.text.strip():
                    prefs.append({"prompt": f"Write section '{s.heading}'.", "chosen": s.text, "rejected": gsec[s.heading],
                                  "source": f"human-edit-section:{d.name}"})
    files = {"c1_requirements.jsonl": c1, "c4_sentences.jsonl": c4, "preference_pairs.jsonl": prefs}
    for name, rows in files.items():
        with (out / name).open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with (out / "sft_c1_chat.jsonl").open("w", encoding="utf-8") as f:
        for r in c1:
            verdict = {"score": 1.0 if r["label"] else 0.3, "defects": r["defects"],
                       "reason": "Testable and specific." if r["label"] else f"Defects: {', '.join(r['defects']) or 'weak'}.",
                       "rewrite_hint": "" if r["label"] else "State the checkable rule, number or named artifact."}
            f.write(json.dumps({"messages": [{"role": "system", "content": C1_SYSTEM},
                                             {"role": "user", "content": f"Section: {r['section']}\nRequirement: {r['text']}"},
                                             {"role": "assistant", "content": json.dumps(verdict)}]}, ensure_ascii=False) + "\n")
    return {k: len(v) for k, v in files.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--out", default=str(ROOT / "training"))
    e.add_argument("--no-synthetic", action="store_true")
    s = sub.add_parser("stats")
    s.add_argument("--out", default=str(ROOT / "training"))
    a = ap.parse_args()
    if a.cmd == "export":
        n = export(a.out, synthetic=not a.no_synthetic)
        print("Wrote " + ", ".join(f"{k}: {v}" for k, v in n.items()) + f" to {a.out}")
    else:
        for f in sorted(Path(a.out).glob("*.jsonl")):
            rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
            pos = sum(1 for r in rows if r.get("label") == 1)
            print(f"{f.name}: {len(rows)} rows" + (f" ({pos} positive)" if "label" in (rows[0] if rows else {}) else ""))


if __name__ == "__main__":
    main()
