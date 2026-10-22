"""
C5 – figure QA.

Runs a figure script (figures.py) under a probe that intercepts every savefig() and measures the drawing
before it is written: text that overlaps other text, labels wider than the box they sit in, arrows that run
through labels, and text cut off at the edge of the axes. The PNGs are still written as normal.

    python quality/figure_qa.py stories/311617/figures.py               # writes figure_qa.json beside it
    python quality/figure_qa.py stories/311617/figures.py --vlm         # also ask a vision model to review each PNG

Exit code 0 = no defects, 2 = defects found, 1 = the script failed.
"""
import argparse
import base64
import json
import os
import runpy
import sys
from pathlib import Path

PAD = 1.5          # px tolerance
MIN_OVERLAP = 0.12  # share of the smaller text box


def _visible_texts(fig):
    out = []
    for t in fig.findobj(match=lambda a: a.__class__.__name__ in ("Text", "Annotation")):
        try:
            if not t.get_visible() or not t.get_text().strip() or t.axes is None and t.figure is None:
                continue
        except Exception:  # noqa: BLE001
            continue
        out.append(t)
    return out


def _inter(a, b):
    w = min(a.x1, b.x1) - max(a.x0, b.x0)
    h = min(a.y1, b.y1) - max(a.y0, b.y0)
    return max(0.0, w) * max(0.0, h)


def inspect(fig):
    """Return a list of defects for one matplotlib figure."""
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    texts = []
    for t in _visible_texts(fig):
        try:
            bb = t.get_window_extent(renderer=r)
        except Exception:  # noqa: BLE001
            continue
        if bb.width < 1 or bb.height < 1:
            continue
        texts.append((t, bb))
    boxes, arrows = [], []
    for ax in fig.axes:
        for p in ax.patches:
            if not p.get_visible():
                continue
            if isinstance(p, FancyArrowPatch):
                try:
                    path = p.get_transform().transform_path(p.get_path())
                    for poly in path.to_polygons(closed_only=False):
                        arrows.append((p, poly))
                except Exception:  # noqa: BLE001
                    pass
            elif isinstance(p, (FancyBboxPatch, Rectangle)):
                try:
                    boxes.append(p.get_window_extent(renderer=r))
                except Exception:  # noqa: BLE001
                    pass
    defects = []
    label = lambda t: t.get_text().replace("\n", " ")[:50]  # noqa: E731
    # 1 text over text
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i][1], texts[j][1]
            ov = _inter(a, b)
            small = min(a.width * a.height, b.width * b.height)
            if small and ov / small > MIN_OVERLAP:
                defects.append({"defect": "text_overlap", "severity": "high",
                                "detail": f"'{label(texts[i][0])}' overlaps '{label(texts[j][0])}' ({ov / small:.0%})"})
    # 2 label wider/taller than its box
    for t, bb in texts:
        cx, cy = (bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2
        inside = [b for b in boxes if b.x0 <= cx <= b.x1 and b.y0 <= cy <= b.y1 and b.width < fig.bbox.width * 0.95]
        if not inside:
            continue
        b = min(inside, key=lambda b: b.width * b.height)
        if bb.x0 < b.x0 - PAD or bb.x1 > b.x1 + PAD or bb.y0 < b.y0 - PAD or bb.y1 > b.y1 + PAD:
            over = max(b.x0 - bb.x0, bb.x1 - b.x1, b.y0 - bb.y0, bb.y1 - b.y1)
            defects.append({"defect": "text_overflows_box", "severity": "high",
                            "detail": f"'{label(t)}' runs {over:.0f}px outside its box – wrap it with \\n or widen the box"})
    # 3 arrow through text
    for p, verts in arrows:
        if len(verts) < 2:
            continue
        pts = []
        for (x0, y0), (x1, y1) in zip(verts[:-1], verts[1:]):
            for k in range(12):
                pts.append((x0 + (x1 - x0) * k / 12, y0 + (y1 - y0) * k / 12))
        for t, bb in texts:
            if any(bb.x0 + 2 < x < bb.x1 - 2 and bb.y0 + 2 < y < bb.y1 - 2 for x, y in pts):
                defects.append({"defect": "arrow_through_text", "severity": "high",
                                "detail": f"an arrow runs through '{label(t)}'"})
    # 4 clipped at the axes edge
    for t, bb in texts:
        ax = t.axes
        if ax is None or not t.get_clip_on():
            continue
        ab = ax.get_window_extent(renderer=r)
        if bb.x0 < ab.x0 - PAD or bb.x1 > ab.x1 + PAD or bb.y0 < ab.y0 - PAD or bb.y1 > ab.y1 + PAD:
            defects.append({"defect": "text_clipped", "severity": "medium", "detail": f"'{label(t)}' is cut off at the plot edge"})
    seen, uniq = set(), []
    for d in defects:
        if d["detail"] not in seen:
            seen.add(d["detail"])
            uniq.append(d)
    return uniq


VLM_PROMPT = ("You review a figure for a requirements document. Check: labels readable and not overlapping, text inside "
              "its boxes, arrows not crossing words, a title that states the point (not 'dashboard'), a legend when colour "
              "carries meaning, and that it matches this description: {desc}. Reply as JSON: {{\"score\": 0-1, "
              "\"defects\": [\"...\"], \"fix\": \"one sentence\"}}")


def vlm_review(png, desc=""):
    """Optional: ask a vision-language model (SLM_VLM_MODEL on the SLM server) to review the image."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from quality import slm
    model = os.environ.get("SLM_VLM_MODEL")
    if not (model and os.environ.get("SLM_BASE_URL")):
        return None
    b64 = base64.b64encode(Path(png).read_bytes()).decode()
    body = {"model": model, "temperature": 0, "max_tokens": 400,
            "messages": [{"role": "user", "content": [{"type": "text", "text": VLM_PROMPT.format(desc=desc)},
                                                      {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]}]}
    headers = {"Authorization": f"Bearer {os.environ['SLM_API_KEY']}"} if os.environ.get("SLM_API_KEY") else {}
    try:
        data = slm._cached("vlm", {"m": model, "img": b64[:2000] + str(len(b64)), "d": desc},
                           lambda: slm._post(os.environ["SLM_BASE_URL"].rstrip("/") + "/chat/completions", body, headers))
        text = data["choices"][0]["message"]["content"]
        import re
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {"raw": text}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def run_script(script):
    """Run figures.py with the probe; return {png_name: [defects]}."""
    import logging
    import matplotlib
    matplotlib.use("Agg")
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
    from matplotlib.figure import Figure
    report = {}
    original = Figure.savefig

    def probe(self, fname, *a, **k):
        name = Path(str(fname)).name
        try:
            report[name] = inspect(self)
        except Exception as e:  # noqa: BLE001
            report[name] = [{"defect": "probe_error", "severity": "low", "detail": str(e)}]
        return original(self, fname, *a, **k)

    Figure.savefig = probe
    script = Path(script).resolve()
    old_cwd, old_argv = os.getcwd(), sys.argv
    try:
        os.chdir(script.parent)
        sys.argv = [str(script)]
        sys.path.insert(0, str(script.parent))
        runpy.run_path(str(script), run_name="__main__")
    finally:
        Figure.savefig = original
        os.chdir(old_cwd)
        sys.argv = old_argv
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("--out", help="report path (default: figure_qa.json beside the script)")
    ap.add_argument("--vlm", action="store_true", help="also review each PNG with SLM_VLM_MODEL")
    ap.add_argument("--plan", help="plan.json, for figure descriptions given to the VLM")
    a = ap.parse_args()
    try:
        report = run_script(a.script)
    except SystemExit as e:
        if e.code not in (0, None):
            print(f"figures script exited with {e.code}")
            sys.exit(1)
        report = {}
    except Exception as e:  # noqa: BLE001
        print(f"figures script failed: {e}")
        sys.exit(1)
    out = {"figures": {k: {"defects": v} for k, v in report.items()}}
    if a.vlm:
        desc = {}
        if a.plan and Path(a.plan).exists():
            desc = {f["file"]: f.get("description", "") for f in json.loads(Path(a.plan).read_text(encoding="utf-8")).get("figures", [])}
        for name in out["figures"]:
            png = Path(a.script).resolve().parent / name
            if png.exists():
                out["figures"][name]["vlm"] = vlm_review(png, desc.get(name, ""))
    n = sum(len(v["defects"]) for v in out["figures"].values())
    out["defects"] = n
    out["high"] = sum(1 for v in out["figures"].values() for d in v["defects"] if d["severity"] == "high")
    target = Path(a.out) if a.out else Path(a.script).resolve().parent / "figure_qa.json"
    target.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    for name, v in out["figures"].items():
        print(f"{name}: {len(v['defects'])} defect(s)")
        for d in v["defects"][:12]:
            print(f"   - [{d['severity']}] {d['defect']}: {d['detail']}")
    sys.exit(2 if out["high"] else 0)


if __name__ == "__main__":
    main()
