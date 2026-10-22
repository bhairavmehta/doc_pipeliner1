"""
Generate research/research_findings.md from the downloaded sources in research/sources/.

Steps
  1. Read every PDF / HTML / TXT file in research/sources (text is cached in research/sources/_text).
  2. For each research question in research/questions.json, find the most relevant passages (keyword ranking).
  3a. Mode "evidence" (no AI needed): write research/research_evidence.md with the passages, cited by file and page.
      A person - or Codex / an approved AI chat using prompts/09_research_findings.md - turns it into findings.
  3b. Mode "llm": send the passages to your company-approved AI endpoint, which writes the findings
      with citations. Output: research/research_findings.md (the previous version is kept as .prev.md).

Usage (VS Code: Terminal > Run Task... > "Research: build evidence" / "Research: write findings with AI")
    python research_findings.py                 # evidence mode (default)
    python research_findings.py --mode llm      # AI mode (needs the LLM_* settings below)
    python research_findings.py --top 10        # passages per question (default 8)

AI settings (environment variables, or a .env file in this folder - never commit keys):
    LLM_PROVIDER   openai | azure | anthropic       (openai = any OpenAI-compatible endpoint, e.g. a company gateway)
    LLM_BASE_URL   e.g. https://api.openai.com/v1
                   Azure: https://<resource>.openai.azure.com/openai/deployments/<deployment>
                   Anthropic: https://api.anthropic.com
    LLM_API_KEY    the key issued for the approved endpoint
    LLM_MODEL      model name (for Azure: the deployment's model; still required)
    LLM_API_VERSION  Azure only, e.g. 2024-06-01

Only public documents from research/sources are sent to the AI. Use an endpoint approved for that data.
AI answers are cached in research/.cache, so re-running gives the same result (delete the cache to refresh).
"""
import argparse
import csv
import datetime as dt
import hashlib
import html.parser
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
RESEARCH = HERE / "research"
SOURCES = RESEARCH / "sources"
TEXT_CACHE = SOURCES / "_text"
LLM_CACHE = RESEARCH / ".cache"
QUESTIONS = RESEARCH / "questions.json"


def set_paths(base):
    """Point the script at another folder's research/ (e.g. stories/123456)."""
    global RESEARCH, SOURCES, TEXT_CACHE, LLM_CACHE, QUESTIONS
    RESEARCH = Path(base) / "research"
    SOURCES = RESEARCH / "sources"
    TEXT_CACHE = SOURCES / "_text"
    LLM_CACHE = RESEARCH / ".cache"
    QUESTIONS = RESEARCH / "questions.json"
CHUNK_CHARS = 1200


# ---------------------------------------------------------------- 1. read sources
class _HTMLText(html.parser.HTMLParser):
    SKIP = {"script", "style", "nav", "footer", "header", "noscript"}

    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag in ("p", "li", "tr", "h1", "h2", "h3", "h4", "div", "br"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def read_pages(path):
    """Return a list of (page_number, text). HTML/TXT count as one page."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            sys.exit("pypdf is missing: run  python -m pip install -r requirements.txt")
        reader = PdfReader(str(path))
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if suffix in (".html", ".htm"):
        p = _HTMLText()
        p.feed(raw)
        raw = "".join(p.parts)
    return [(1, raw)]


def load_documents():
    if not SOURCES.exists():
        sys.exit(f"No sources found. Put the source papers (PDF/HTML/TXT) in {SOURCES}.")
    TEXT_CACHE.mkdir(parents=True, exist_ok=True)
    docs = {}
    for f in sorted(SOURCES.iterdir()):
        if f.suffix.lower() not in (".pdf", ".html", ".htm", ".txt") or f.name.endswith("_NOT_A_PDF.html"):
            continue
        cache = TEXT_CACHE / (f.name + ".json")
        if cache.exists() and cache.stat().st_mtime >= f.stat().st_mtime:
            pages = json.loads(cache.read_text(encoding="utf-8"))
        else:
            try:
                pages = read_pages(f)
            except Exception as e:  # damaged or protected file
                print(f"[skip] {f.name}: could not read ({e})")
                continue
            cache.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
        docs[f.name] = pages
        print(f"[read] {f.name}  ({len(pages)} page{'s' if len(pages) != 1 else ''})")
    if not docs:
        sys.exit("research/sources has no readable PDF/HTML/TXT files.")
    return docs


# ---------------------------------------------------------------- 2. find passages
def chunks(docs):
    out = []
    for name, pages in docs.items():
        for page_no, text in pages:
            text = re.sub(r"[ \t]+", " ", text)
            paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=[A-Z0-9•\-])", text) if p.strip()]
            buf = ""
            for para in paras:
                if len(buf) + len(para) > CHUNK_CHARS and buf:
                    out.append({"file": name, "page": page_no, "text": buf.strip()})
                    buf = ""
                buf += " " + para
            if len(buf.strip()) > 80:
                out.append({"file": name, "page": page_no, "text": buf.strip()})
    return out


def tokens(text):
    return re.findall(r"[a-z0-9][a-z0-9\-]+", text.lower())


def rank(all_chunks, query_terms, top):
    """BM25 ranking; keeps at most 3 passages per file so several sources are represented."""
    docs_tok = [Counter(tokens(c["text"])) for c in all_chunks]
    n = len(docs_tok)
    avg = sum(sum(d.values()) for d in docs_tok) / max(n, 1)
    q = []
    for term in query_terms:
        q += tokens(term)
    q = list(dict.fromkeys(q))
    df = {t: sum(1 for d in docs_tok if t in d) for t in q}
    scores = []
    for i, d in enumerate(docs_tok):
        length = sum(d.values())
        s = 0.0
        for t in q:
            if t in d:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * d[t] * 2.2 / (d[t] + 1.2 * (0.25 + 0.75 * length / avg))
        scores.append((s, i))
    picked, per_file = [], Counter()
    for s, i in sorted(scores, reverse=True):
        c = all_chunks[i]
        if s <= 0 or per_file[c["file"]] >= 3:
            continue
        picked.append(dict(c, score=round(s, 2)))
        per_file[c["file"]] += 1
        if len(picked) == top:
            break
    return picked


def cite(c):
    return f"[{c['file']}, p.{c['page']}]" if c["file"].lower().endswith(".pdf") else f"[{c['file']}]"


# ---------------------------------------------------------------- 3b. call the AI
def load_env():
    env_file = HERE / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def call_llm(system, user):
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()
    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    key, model = os.environ.get("LLM_API_KEY"), os.environ.get("LLM_MODEL")
    if not key or not model:
        sys.exit("Set LLM_API_KEY and LLM_MODEL (and LLM_PROVIDER / LLM_BASE_URL) - see the top of this file.")

    LLM_CACHE.mkdir(parents=True, exist_ok=True)
    cache = LLM_CACHE / (hashlib.sha256(f"{provider}|{model}|{system}|{user}".encode()).hexdigest() + ".txt")
    if cache.exists():
        return cache.read_text(encoding="utf-8")

    if provider == "anthropic":
        url = base + "/v1/messages"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        body = {"model": model, "max_tokens": 2000, "temperature": 0, "system": system,
                "messages": [{"role": "user", "content": user}]}
    else:
        url = base + "/chat/completions"
        headers = {"Authorization": f"Bearer {key}"}
        if provider == "azure":
            url += "?api-version=" + os.environ.get("LLM_API_VERSION", "2024-06-01")
            headers = {"api-key": key}
        body = {"model": model, "temperature": 0, "max_tokens": 2000,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}

    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={**headers, "Content-Type": "application/json"})
    try:
        import truststore  # optional: company certificate store
        import ssl
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        ctx = None
    try:
        with urllib.request.urlopen(req, timeout=180, context=ctx) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"AI endpoint returned HTTP {e.code}: {e.read()[:500]!r}")
    except Exception as e:
        sys.exit(f"Could not reach the AI endpoint ({e}). Check LLM_BASE_URL, the proxy, or use evidence mode.")
    text = data["content"][0]["text"] if provider == "anthropic" else data["choices"][0]["message"]["content"]
    cache.write_text(text, encoding="utf-8")
    return text


SYSTEM = (
    "You are a careful research analyst. Write short, plain-English findings for a requirements "
    "document. Use ONLY the numbered passages provided. After every finding, cite the passage source exactly "
    "as given in square brackets, e.g. [paper_name.pdf, p.12]. If the passages do not "
    "answer part of the question, write 'Not found in the downloaded sources - to be confirmed.' Never use "
    "outside knowledge. Output Markdown bullets only, no heading."
)


def llm_findings(q, passages):
    blocks = "\n\n".join(f"Passage {i + 1} {cite(c)}:\n{c['text']}" for i, c in enumerate(passages))
    user = (f"Research question: {q['question']}\n\nWrite 3-8 bullet findings that answer it, "
            f"each with its citation.\n\nPassages:\n{blocks}")
    return call_llm(SYSTEM, user).strip()


# ---------------------------------------------------------------- output
def sources_table():
    manifest = SOURCES / "manifest.csv"
    lines = ["| File | Link | Downloaded |", "|---|---|---|"]
    if manifest.exists():
        with manifest.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["status"] == "OK":
                    lines.append(f"| {r['file']} | {r['url']} | {r['downloaded'][:10]} |")
    for f in sorted(SOURCES.glob("*")):
        if (f.is_file() and f.suffix.lower() in (".pdf", ".html", ".txt")
                and not f.name.endswith("_NOT_A_PDF.html") and f.name not in "\n".join(lines)):
            lines.append(f"| {f.name} | added by hand | {dt.date.fromtimestamp(f.stat().st_mtime)} |")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["evidence", "llm"], default="evidence")
    ap.add_argument("--top", type=int, default=8, help="passages per question")
    ap.add_argument("--workdir", help="folder that contains research/ (default: this folder); used by run_pipeline.py")
    args = ap.parse_args()
    if args.workdir:
        set_paths(Path(args.workdir))

    cfg = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    docs = load_documents()
    all_chunks = chunks(docs)
    print(f"Indexed {len(all_chunks)} passages from {len(docs)} files.\n")
    today = dt.date.today().isoformat()

    sys.path.insert(0, str(HERE))
    from quality import retrieval as K3
    print(f"Retrieval: {K3.mode()}")

    def find(q):
        return K3.rank(all_chunks, [q["question"]] + q["keywords"], args.top, rank, question=q["question"])

    if args.mode == "evidence":
        out = [f"# Research Evidence – {cfg['title'].split('–', 1)[-1].strip()}", "",
               f"Generated {today} by research_findings.py (evidence mode) from {len(docs)} files in research/sources.",
               "Next step: turn this into research_findings.md with prompts/09_research_findings.md "
               "(Codex or an approved AI chat), or by hand.", ""]
        for q in cfg["questions"]:
            found = find(q)
            out += [f"## {q['heading']}", "", f"**Question:** {q['question']}", ""]
            if not found:
                out += ["_No relevant passages found in the downloaded sources._", ""]
            for c in found:
                quote = re.sub(r"\s+", " ", c["text"])[:900]
                out += [f"- {cite(c)} (score {c['score']})", f"  > {quote}", ""]
            print(f"{q['id']}: {len(found)} passages")
        out += ["## Sources", ""] + sources_table()
        target = RESEARCH / "research_evidence.md"
    else:
        load_env()
        out = [f"# {cfg['title']}", "",
               f"Generated {today} by research_findings.py from {len(docs)} downloaded sources (research/sources). "
               f"Purpose: {cfg['purpose']}",
               "Every finding cites its source file and page. Check key facts against the documents before use.", ""]
        weak = []
        for q in cfg["questions"]:
            found = find(q)
            print(f"{q['id']}: {len(found)} passages -> asking the AI ...")
            out += [f"## {q['heading']}", ""]
            if not found:
                out += ["- Not found in the downloaded sources - to be confirmed.", ""]
                weak.append(q["heading"])
                continue
            text = llm_findings(q, found)
            if "to be confirmed" in text.lower():
                weak.append(q["heading"])
            out += [text, ""]
        out += ["## Caveats", "",
                "- Findings were drafted by an AI from the passages listed and must be checked by a person.",
                "- Only documents in research/sources were used; newer documents may exist."]
        out += [f"- Gaps to confirm: {', '.join(weak)}." if weak else "- No gaps were flagged by the AI."]
        out += ["", "## Key sources", ""] + sources_table()
        target = RESEARCH / "research_findings.md"
        if target.exists():
            target.replace(RESEARCH / "research_findings.prev.md")

    target.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\nWrote {target}")


if __name__ == "__main__":
    main()
