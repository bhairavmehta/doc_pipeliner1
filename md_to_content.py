"""
Convert a Markdown draft (e.g. an AI assistant's reply saved as content.md) into content.json.

Usage:
    python md_to_content.py                         # content.md -> content.json
    python md_to_content.py my_draft.md my.json     # custom names

Markdown format (see prompts/08_markdown_format.md):
    ---                      front matter: title / subtitle / footer
    # Heading                heading1          ## Heading   heading2
    Plain text               paragraph         > text       grey note paragraph
    - item                   bullets           ```          code block
    | a | b |  (pipe table)  table             ![Caption](file.png){width=6.5}  image
    <!-- widths: 0.6, 5.2, 0.7 -->   optional column widths (inches) for the next table
    **ID** in every first-column cell  -> first column shown in bold
"""
import json
import re
import sys
from pathlib import Path

PAGE_WIDTH = 6.5
IMG_RE = re.compile(r"^!\[(?P<cap>[^\]]*)\]\((?P<file>[^)]+)\)(\{width=(?P<w>[\d.]+)\})?\s*$")
WIDTHS_RE = re.compile(r"^<!--\s*widths:\s*([\d.,\s]+)-->\s*$")
COMMENT_RE = re.compile(r"^<!--.*-->\s*$")


def clean(text):
    """Remove inline bold/italic markers an AI may add; the layout script does the styling."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip()


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells = re.split(r"(?<!\\)\|", line)
    return [c.strip().replace("\\|", "|") for c in cells]


def auto_widths(columns, rows):
    """Share the page width by typical text length per column (min 0.75 in)."""
    n = len(columns)
    weights = []
    for i in range(n):
        lengths = [len(columns[i])] + [len(r[i]) for r in rows if i < len(r)]
        avg = sum(lengths) / len(lengths)
        weights.append(min(max(avg, 4), 120))
    total = sum(weights)
    widths = [max(0.75, PAGE_WIDTH * w / total) for w in weights]
    scale = PAGE_WIDTH / sum(widths)
    return [round(w * scale, 2) for w in widths]


def parse(md_text):
    lines = md_text.splitlines()
    cfg = {"title": "", "subtitle": "", "footer": "", "blocks": []}
    i = 0
    # front matter
    if lines and lines[0].strip() == "---":
        i = 1
        while i < len(lines) and lines[i].strip() != "---":
            if ":" in lines[i]:
                key, val = lines[i].split(":", 1)
                if key.strip() in ("title", "subtitle", "footer", "logo"):
                    cfg[key.strip()] = val.strip()
            i += 1
        i += 1
    blocks = cfg["blocks"]
    pending_widths = None
    para = []

    def flush_para():
        if para:
            blocks.append({"type": "paragraph", "text": clean(" ".join(para))})
            para.clear()

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        if not line:
            flush_para(); i += 1; continue

        m = WIDTHS_RE.match(line)
        if m:
            flush_para()
            pending_widths = [float(x) for x in m.group(1).split(",") if x.strip()]
            i += 1; continue
        if COMMENT_RE.match(line):
            i += 1; continue

        if line.startswith("```"):
            flush_para()
            code, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i].rstrip()); i += 1
            blocks.append({"type": "code", "lines": code})
            i += 1; continue

        if line.startswith("#"):
            flush_para()
            level = len(line) - len(line.lstrip("#"))
            blocks.append({"type": "heading1" if level == 1 else "heading2", "text": clean(line.lstrip("#"))})
            i += 1; continue

        if line.startswith(">"):
            flush_para()
            note = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                note.append(lines[i].strip().lstrip(">").strip()); i += 1
            blocks.append({"type": "paragraph", "text": clean(" ".join(note)), "style": "note"})
            continue

        if re.match(r"^[-*+]\s+", line) or re.match(r"^\d+[.)]\s+", line):
            flush_para()
            items = []
            while i < len(lines):
                s = lines[i].strip()
                m = re.match(r"^(?:[-*+]|\d+[.)])\s+(.*)$", s)
                if m:
                    items.append(clean(m.group(1)))
                elif s and items and lines[i].startswith((" ", "\t")):
                    items[-1] += " " + clean(s)          # wrapped bullet line
                else:
                    break
                i += 1
            blocks.append({"type": "bullets", "items": items})
            continue

        if line.startswith("|"):
            flush_para()
            table = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table.append(lines[i]); i += 1
            columns = [clean(c) for c in split_row(table[0])]
            body = [r for r in table[1:] if not re.match(r"^\|?\s*:?-{2,}", r.strip())]
            rows_raw = [split_row(r) for r in body]
            rows_raw = [(r + [""] * len(columns))[:len(columns)] for r in rows_raw]
            first = [r[0] for r in rows_raw if r[0]]
            bold_first = bool(first) and all(c.startswith("**") and c.endswith("**") for c in first)
            rows = [[clean(c) for c in r] for r in rows_raw]
            widths = pending_widths if pending_widths and len(pending_widths) == len(columns) else auto_widths(columns, rows)
            pending_widths = None
            blocks.append({"type": "table", "columns": columns, "widths_in": widths,
                           "bold_first_column": bold_first, "rows": rows})
            continue

        m = IMG_RE.match(line)
        if m:
            flush_para()
            blocks.append({"type": "image", "file": m.group("file"),
                           "width_in": float(m.group("w") or PAGE_WIDTH), "caption": clean(m.group("cap"))})
            i += 1; continue

        para.append(line)
        i += 1

    flush_para()
    if not cfg.get("logo"):
        cfg.pop("logo", None)
    if not cfg["title"]:
        h = next((b for b in blocks if b["type"] == "heading1"), None)
        cfg["title"] = h["text"] if h else "Untitled"
    return cfg


if __name__ == "__main__":
    here = Path(__file__).parent
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "content.md"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".json")
    cfg = parse(src.read_text(encoding="utf-8"))
    dst.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    counts = {}
    for b in cfg["blocks"]:
        counts[b["type"]] = counts.get(b["type"], 0) + 1
    print(f"Wrote {dst.name}: {len(cfg['blocks'])} blocks {counts}")
