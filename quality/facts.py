"""
K1 – fact ledger.

Splits research_findings.md (and any inputs/_text/*.txt) into atomic, numbered facts. Each fact carries the
key terms that must appear in a document for the fact to count as used: versions, numbers, codes, named
methods and bold phrases. The plan assigns every fact to a section, and critic C3 measures recall against it.

    python quality/facts.py stories/311617/research_findings.md            # writes facts.jsonl + facts.md beside it
    python quality/facts.py research_findings.md --out stories/311617      # choose the output folder
    python quality/facts.py research_findings.md --slm                     # let the small model split long bullets
    python quality/facts.py research_findings.md --check content.md        # show which facts a document uses
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from quality import slm  # noqa: E402

STOP_CODES = {"A", "I", "AN", "OR", "AND", "THE", "OK", "US", "PDF", "CSV", "API", "AI", "LLM", "LLMS", "URL", "NOT",
              "TO", "BE", "IS", "IN", "OF", "ON", "FOR", "NO", "VS", "EG", "IE", "HTML", "JSON", "Q1", "Q2", "Q3", "Q4"}
ABBREV = r"(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\bp)(?<!\bNo)(?<!\bv\d)"
SENT_SPLIT = re.compile(ABBREV + r"(?<=[.!?])\s+(?=[A-Z\*\"“(])")


def _norm(s):
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("–", "-").replace("—", "-")).strip()


def extract_keys(text):
    """Salient terms, most distinctive first."""
    keys = []
    for b in re.findall(r"\*\*(.+?)\*\*", text):
        b = re.sub(r"[()]", "", b).strip()
        if 2 < len(b) < 60:
            keys.append(("phrase", b.lower()))
    plain = re.sub(r"\*\*", "", text)
    plain = re.sub(r"https?://\S+", "", plain)
    for v in re.findall(r"\bv\d+(?:\.\d+)+\b", plain, re.I):
        keys.append(("version", v.lower()))
    for n in re.findall(r"\b[A-Z][a-z]+[A-Z][A-Za-z]+\b|\b[A-Za-z]+-[A-Z]{2,}[A-Za-z]*\b|\b[A-Z][a-z]+[A-Z]{2,}\b", plain):
        keys.append(("name", n))
    for c in re.findall(r"(?<![\w-])[A-Z][A-Z0-9]{1,6}(?:-[A-Z0-9]{1,4})?(?![\w-])", plain):
        if c not in STOP_CODES and not re.fullmatch(r"\d+", c):
            keys.append(("code", c))
    for n in re.findall(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?![\d])|(?<![\w.])\d+(?:\.\d+)?\s?%|(?<![\w.v])\d{2,}(?:\.\d+)?(?![\w])", plain):
        keys.append(("number", n.replace(" ", "")))
    seen, out = set(), []
    for k in keys:
        if k[1].lower() not in seen:
            seen.add(k[1].lower())
            out.append(k)
    order = {"phrase": 0, "version": 1, "name": 2, "number": 3, "code": 4}
    out.sort(key=lambda k: order[k[0]])
    return out[:6]


def _rows(table_lines):
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in table_lines]
    rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r if c)]
    return rows[0], rows[1:]


def build(findings_text, extra_texts=(), use_slm=False):
    facts, sources = [], []
    section = ""
    lines = findings_text.splitlines()
    i = 0

    def add(text, kind="finding"):
        text = _norm(text)
        if len(text.split()) < 4:
            return
        keys = extract_keys(text)
        facts.append({"id": f"F-{len(facts) + 1:03d}", "section": section, "kind": kind, "text": re.sub(r"\*\*", "", text),
                      "keys": [k for _, k in keys], "key_types": [t for t, _ in keys]})

    while i < len(lines):
        line = lines[i].rstrip()
        h = re.match(r"^#{2,3}\s+(.*)", line)
        if h:
            section = h.group(1).strip()
            i += 1
            continue
        low = section.lower()
        if "key sources" in low or low.startswith("sources") or low == "references":
            m = re.match(r"^\s*[-*]\s+(.*?):?\s*(https?://\S+)", line)
            if m:
                sources.append({"title": m.group(1).strip(" :–-"), "url": m.group(2)})
            elif re.match(r"^\s*[-*]\s+\S", line):
                sources.append({"title": re.sub(r"^\s*[-*]\s+", "", line).strip(), "url": ""})
            i += 1
            continue
        kind = "caveat" if "caveat" in low else "finding"
        if line.strip().startswith("|"):
            tbl = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                tbl.append(lines[i])
                i += 1
            head, rows = _rows(tbl)
            for r in rows:
                parts = [f"{head[j]}: {c}" if j and j < len(head) else c for j, c in enumerate(r) if c]
                add("; ".join(parts), kind)
            continue
        m = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(.*)", line)
        if m:
            item = m.group(1)
            while i + 1 < len(lines) and lines[i + 1].startswith(("  ", "\t")) and lines[i + 1].strip() \
                    and not re.match(r"^\s*(?:[-*]|\d+[.)])\s+", lines[i + 1]):
                i += 1
                item += " " + lines[i].strip()
            parts = _split_slm(item) if use_slm and len(item.split()) > 35 else None
            if not parts:
                lead = re.match(r"^\*\*([^*]+)\*\*:?\s*(.*)$", item)   # "**TnT-LLM (…):** text" keeps its label on every part
                label, rest = (lead.group(1).strip(" :"), lead.group(2)) if lead else ("", item)
                parts = [p for p in SENT_SPLIT.split(rest) if p.strip()]
                if label:
                    parts = [f"**{label}**: {p}" for p in parts] or [f"**{label}**"]
            for p in parts:
                add(p, kind)
        elif line.strip() and not line.startswith("#") and section and kind == "caveat":
            add(line, kind)
        i += 1
    for name, t in extra_texts:
        for para in re.split(r"\n\s*\n", t):
            if 8 <= len(para.split()) <= 80:
                section = f"input: {name}"
                add(para, "input")
    return facts, sources


def _split_slm(text):
    if not slm.enabled():
        return None
    try:
        out = slm.chat_json(
            "Split the finding into atomic claims. Each claim states one fact and keeps every number, version, code "
            "and name it needs. Do not add facts. Reply as JSON: {\"claims\": [\"...\"]}.", text)
        claims = [c for c in out.get("claims", []) if isinstance(c, str) and c.strip()]
        return claims or None
    except slm.SLMError:
        return None


# ---------------------------------------------------------------- usage check
def _present(key, text_low, text):
    k = key.lower()
    if re.fullmatch(r"[\d,.]+%?", k):
        k2 = k.replace(",", "")
        return bool(re.search(r"(?<![\d.])" + re.escape(k) + r"(?![\d])", text_low)
                    or re.search(r"(?<![\d.])" + re.escape(k2) + r"(?![\d])", text_low.replace(",", "")))
    if re.fullmatch(r"[A-Z0-9\-]+", key):
        return bool(re.search(r"(?<![\w-])" + re.escape(key) + r"(?![\w-])", text))
    if " " in k and len(k.split()) > 2:          # long bold phrase: accept if most content words appear
        ws = [w for w in re.findall(r"[a-z0-9.\-]+", k) if len(w) > 3]
        return bool(ws) and sum(w in text_low for w in ws) / len(ws) >= 0.6
    return k in text_low


def distinctive_keys(facts, common_text=""):
    """Keys that identify a fact: drop terms shared by 3+ facts or already in the story (e.g. CICTT, ICAO, 2026)."""
    df = {}
    for f in facts:
        for k in set(x.lower() for x in f["keys"]):
            df[k] = df.get(k, 0) + 1
    ct = common_text.lower()
    out = {}
    for f in facts:
        ks = [k for k in f["keys"] if df.get(k.lower(), 0) <= 2 and not (len(k) < 30 and _present(k, ct, common_text))]
        out[f["id"]] = ks
    return out


def fact_used(fact, text, text_low=None, keys=None):
    keys = fact["keys"] if keys is None else keys
    tl = text_low or text.lower()
    if not keys:
        stop = {"which", "their", "there", "these", "those", "about", "other", "would", "should", "could", "where"}
        ws = [w for w in dict.fromkeys(re.findall(r"[a-z][a-z\-]{4,}", fact["text"].lower())) if w not in stop]
        return bool(ws) and sum(bool(re.search(r"\b" + re.escape(w), tl)) for w in ws) / len(ws) >= 0.7
    hits = sum(_present(k, tl, text) for k in keys)
    return hits >= max(1, -(-len(keys) * 6 // 10))   # ceil(60%)


def recall(facts, text, ids=None, common_text=""):
    tl = text.lower()
    dk = distinctive_keys(facts, common_text)
    pool = [f for f in facts if (ids is None or f["id"] in ids) and f["kind"] != "input"]
    used = [f["id"] for f in pool if fact_used(f, text, tl, dk[f["id"]])]
    return (len(used) / len(pool) if pool else 1.0), used, [f["id"] for f in pool if f["id"] not in used]


def source_recall(sources, references_text):
    """Share of the findings' key sources that the References section names (by domain + path or by title words)."""
    if not sources:
        return 1.0, []
    rt = references_text.lower()
    missing = []
    for s in sources:
        url = s["url"].lower().split("://", 1)[-1].rstrip("/")
        domain = url.split("/")[0].replace("www.", "")
        tail = url.split("/")[-1][:30]
        title_words = [w for w in re.findall(r"[a-z0-9\-_.]{4,}", s["title"].lower())][:4]
        by_url = bool(url) and domain in rt and (tail in rt or sum(w in rt for w in title_words) >= max(1, len(title_words) // 2))
        by_title = bool(title_words) and sum(w in rt for w in title_words) >= max(1 if not url else 2, len(title_words) - 1)
        ok = by_url or by_title
        if not ok:
            missing.append(s["title"])
    return 1 - len(missing) / len(sources), missing


# ---------------------------------------------------------------- io
def write(facts, sources, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "facts.jsonl").open("w", encoding="utf-8") as f:
        for x in facts:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    (out_dir / "sources.json").write_text(json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["# Fact ledger", "", f"{len(facts)} facts from the research findings. Every fact is assigned to a section in "
          "plan.json (or listed as unused with a reason). Key terms in brackets must appear when the fact is used.", ""]
    cur = None
    for x in facts:
        if x["section"] != cur:
            cur = x["section"]
            md += ["", f"## {cur or '(no section)'}", ""]
        md.append(f"- **{x['id']}** {x['text']}  [keys: {', '.join(x['keys']) or '–'}]")
    md += ["", "## Key sources", ""] + [f"- {s['title']}: {s['url']}" for s in sources]
    (out_dir / "facts.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return out_dir / "facts.jsonl", out_dir / "facts.md"


def load(story_dir):
    p = Path(story_dir) / "facts.jsonl"
    if not p.exists():
        return [], []
    facts = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    s = Path(story_dir) / "sources.json"
    return facts, (json.loads(s.read_text(encoding="utf-8")) if s.exists() else [])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("findings")
    ap.add_argument("--out", help="output folder (default: beside the findings file)")
    ap.add_argument("--inputs", help="folder of extra .txt inputs to add as facts")
    ap.add_argument("--slm", action="store_true", help="split long bullets with the small model (needs SLM_* settings)")
    ap.add_argument("--check", help="a .md or .docx document: report which facts it uses")
    ap.add_argument("--story", help="story file: its terms are treated as common, not as evidence of fact use")
    a = ap.parse_args()
    extra = [(f.name, f.read_text(encoding="utf-8", errors="ignore")) for f in Path(a.inputs).glob("*.txt")] if a.inputs else []
    facts, sources = build(Path(a.findings).read_text(encoding="utf-8"), extra, a.slm)
    if a.check:
        from quality.doc_model import load as load_doc
        doc = load_doc(a.check)
        common = Path(a.story).read_text(encoding="utf-8") if a.story else ""
        r, used, missing = recall(facts, doc.text, common_text=common)
        sr, smiss = source_recall(sources, "\n".join(doc.references()))
        print(f"{len(facts)} facts; used {len(used)} ({r:.0%}); key sources cited {sr:.0%}")
        for f in facts:
            print(f"  {'✔' if f['id'] in used else '✘'} {f['id']} {f['text'][:100]}  [{', '.join(f['keys'])}]")
        return
    j, m = write(facts, sources, a.out or Path(a.findings).parent)
    print(f"Wrote {j} and {m}: {len(facts)} facts, {len(sources)} key sources")


if __name__ == "__main__":
    main()
