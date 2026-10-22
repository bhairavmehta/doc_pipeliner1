"""
Parse a pipeline Markdown document into a structure the critics can reason about:
sections (with their raw text, tables and bullets), requirement rows, decision sections,
figures, citations and references.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import md_to_content  # noqa: E402

REQ_ID = re.compile(r"^[A-Z][A-Z0-9]{0,6}-\d+[a-z]?$")
CITE = re.compile(r"\[([^\[\]]+?\.(?:pdf|html?|txt|md|json|docx))(?:,\s*(?:p\.?\s*|page\s*)(\d+))?[^\[\]]*\]", re.I)
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9’'\-\.]*")


def words(text):
    return WORD.findall(text or "")


class Section:
    def __init__(self, heading, number):
        self.heading = heading
        self.number = number
        self.blocks = []
        self.raw_lines = []

    @property
    def text(self):
        return "\n".join(self.raw_lines)

    @property
    def tables(self):
        return [b for b in self.blocks if b["type"] == "table"]

    @property
    def requirements(self):
        out = []
        for t in self.tables:
            cols = [c.lower() for c in t["columns"]]
            if not cols or cols[0] not in ("id", "req", "req id", "requirement id"):
                continue
            ri = next((i for i, c in enumerate(cols) if "requirement" in c), 1 if len(cols) > 1 else 0)
            pi = next((i for i, c in enumerate(cols) if "priority" in c), None)
            for r in t["rows"]:
                if r and REQ_ID.match(r[0].strip()):
                    out.append({"id": r[0].strip(), "text": r[ri] if ri < len(r) else "",
                                "priority": (r[pi] if pi is not None and pi < len(r) else ""), "section": self.heading})
        return out

    @property
    def is_decision(self):
        return "(decision)" in self.heading.lower()

    def word_count(self):
        return len(words(self.text))


class Doc:
    def __init__(self, md_text):
        self.md = md_text
        self.cfg = md_to_content.parse(md_text)
        self.sections = []
        self.preamble = Section("(front)", 0)
        self._split()

    def _split(self):
        # raw text per section (for keyword checks, tables kept as pipe text)
        body = self.md
        if body.lstrip().startswith("---"):
            parts = body.split("---", 2)
            body = parts[2] if len(parts) == 3 else body
        cur = self.preamble
        for line in body.splitlines():
            if re.match(r"^#\s+", line):
                h = line.lstrip("#").strip()
                m = re.match(r"^(\d+)[.)]?\s", h)
                cur = Section(h, int(m.group(1)) if m else None)
                self.sections.append(cur)
            else:
                cur.raw_lines.append(line)
        # parsed blocks per section
        idx = -1
        for b in self.cfg["blocks"]:
            if b["type"] == "heading1":
                idx += 1
                continue
            (self.sections[idx] if idx >= 0 and idx < len(self.sections) else self.preamble).blocks.append(b)

    # ---------------------------------------------------------------- views
    @property
    def text(self):
        return self.md

    def plain_text(self):
        t = re.sub(r"^---.*?---", "", self.md, flags=re.S)
        t = re.sub(r"[|*#>`]", " ", t)
        return re.sub(r"\s+", " ", t)

    def word_count(self):
        return len(words(self.plain_text()))

    @property
    def requirements(self):
        return [r for s in self.sections for r in s.requirements]

    @property
    def tables(self):
        return [b for b in self.cfg["blocks"] if b["type"] == "table"]

    @property
    def figures(self):
        return [b for b in self.cfg["blocks"] if b["type"] == "image"]

    def citations(self):
        return [(m.group(1), int(m.group(2)) if m.group(2) else None, m.group(0)) for m in CITE.finditer(self.md)]

    def section(self, number):
        return next((s for s in self.sections if s.number == number), None)

    def references(self):
        sec = next((s for s in self.sections if re.search(r"reference|bibliograph|key sources", s.heading, re.I)), None)
        if not sec:
            return []
        items = []
        for b in sec.blocks:
            if b["type"] == "bullets":
                items += b["items"]
            elif b["type"] == "paragraph" and b.get("style") != "note":
                items.append(b["text"])
        return items

    def ask_table(self):
        for b in self.preamble.blocks + (self.sections[0].blocks if self.sections else []):
            if b["type"] == "table" and [c.lower() for c in b["columns"][:2]] == ["ask", "section"]:
                return b
        return None


def load(path):
    p = Path(path)
    if p.suffix.lower() == ".docx":
        from quality.docx_to_md import convert
        md, _ = convert(p)
        return Doc(md)
    return Doc(p.read_text(encoding="utf-8"))
