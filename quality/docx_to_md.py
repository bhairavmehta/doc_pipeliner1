"""
Convert a Word document into the pipeline's Markdown format (front matter, # sections, pipe tables, images).

Used to turn a reviewed gold document into an example / benchmark, and to score any .docx with evaluate.py.

    python quality/docx_to_md.py gold.docx examples/gold/US311617/US311617_benchmark.md
    python quality/docx_to_md.py newdoc.docx out.md --no-images
"""
import argparse
import re
import sys
from pathlib import Path

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

ID_CELL = re.compile(r"^[A-Z][A-Z0-9]{0,6}-\d+[a-z]?$")


def _style(el):
    st = el.find(".//" + qn("w:pStyle"))
    return st.get(qn("w:val")) if st is not None else ""


def _cell(text):
    return re.sub(r"\s+", " ", text.replace("|", "/")).strip()


def convert(path, image_dir=None, image_prefix="fig"):
    """Return (markdown_text, list_of_written_images)."""
    d = docx.Document(str(path))
    rels = d.part.rels
    lines, images, fig_no = [], [], 0
    title = subtitle = ""
    seen_heading = False
    pending_image = None
    body = list(d.element.body.iterchildren())
    for el in body:
        if el.tag == qn("w:p"):
            p = Paragraph(el, d)
            text = p.text.strip()
            style = _style(el)
            blips = el.findall(".//" + qn("a:blip"))
            if blips:
                fig_no += 1
                name = f"{image_prefix}{fig_no}.png"
                rid = blips[0].get(qn("r:embed"))
                if image_dir and rid in rels:
                    Path(image_dir).mkdir(parents=True, exist_ok=True)
                    (Path(image_dir) / name).write_bytes(rels[rid].target_part.blob)
                    images.append(name)
                pending_image = name
                if not text:
                    continue
            if not text:
                continue
            if pending_image:
                cap = text if re.match(r"^(Figure|Fig\.)\s*\d+", text) else f"Figure {fig_no}."
                lines += [f"![{cap}]({pending_image})", ""]
                pending_image = None
                if cap == text:
                    continue
            level = None
            m = re.match(r"Heading(\d)", style)
            if m:
                level = int(m.group(1))
            if level is None and not seen_heading:
                if not title:
                    title = text
                    continue
                if not subtitle:
                    subtitle = text
                    continue
            if lines and lines[-1].startswith("- ") and not (style.startswith("List") or
                                                         (p._p.pPr is not None and p._p.pPr.numPr is not None)):
                lines.append("")
            if level:
                seen_heading = True
                lines += [("#" if level == 1 else "##") + " " + text, ""]
            elif style.startswith("List") or p._p.pPr is not None and p._p.pPr.numPr is not None:
                lines.append(f"- {text}")
            elif style in ("Quote", "IntenseQuote") or text.startswith("Caveat:"):
                lines += [f"> {text}", ""]
            else:
                lines += [text, ""]
        elif el.tag == qn("w:tbl"):
            if pending_image:
                lines += [f"![Figure {fig_no}.]({pending_image})", ""]
                pending_image = None
            t = Table(el, d)
            rows = []
            for r in t.rows:
                cells, last = [], None
                for c in r.cells:            # merged cells repeat; keep one
                    if c._tc is last:
                        continue
                    last = c._tc
                    cells.append(_cell(c.text))
                rows.append(cells)
            if not rows:
                continue
            n = max(len(r) for r in rows)
            rows = [(r + [""] * n)[:n] for r in rows]
            bold = all(ID_CELL.match(r[0]) or (r[0] and len(r[0]) < 40) for r in rows[1:] if r[0])
            if lines and lines[-1].startswith("- "):
                lines.append("")
            lines.append("| " + " | ".join(rows[0]) + " |")
            lines.append("|" + "---|" * n)
            for r in rows[1:]:
                first = f"**{r[0]}**" if bold and r[0] else r[0]
                lines.append("| " + " | ".join([first] + r[1:]) + " |")
            lines.append("")
    if pending_image:
        lines += [f"![Figure {fig_no}.]({pending_image})", ""]
    footer = re.sub(r"\s*\(v\d+\)\s*$", "", title)
    sid = re.search(r"\b(\d{5,8})\b", subtitle + " " + title)
    if sid:
        footer = f"US {sid.group(1)} · {footer}"
    head = ["---", f"title: {title}", f"subtitle: {subtitle}", f"footer: {footer}", "---", ""]
    text = "\n".join(head + lines)
    return re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n", images


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("docx")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--no-images", action="store_true", help="do not extract images")
    a = ap.parse_args()
    out = Path(a.out) if a.out else Path(a.docx).with_suffix(".md")
    md, imgs = convert(a.docx, None if a.no_images else out.parent)
    out.write_text(md, encoding="utf-8")
    print(f"Wrote {out} ({len(md.split())} words, {len(imgs)} image(s))")


if __name__ == "__main__":
    sys.exit(main())
