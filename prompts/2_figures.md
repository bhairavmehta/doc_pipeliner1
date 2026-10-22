PIPELINE STEP: figures

Write a Python script {STORY_DIR}/figures.py that draws every figure listed in {STORY_DIR}/plan.json ("figures") and saves each PNG with exactly the file name given, into the same folder as the script.

Requirements:
- Use matplotlib only (Agg backend). Save with dpi=200, bbox_inches="tight", white background.
- Locate the output folder with Path(__file__).parent so the script works from any working directory.
- Follow the visual style of figure_style.py in the project root: rounded boxes with centred text, arrows between them, colours navy #1F3864, blue #2F5496 / #4472C4, light blue #D9E2F3, grey #595959, amber #C55A11, sand #FBE5D6, green #E2EFDA / #375623. Font: ["Calibri", "Carlito", "DejaVu Sans"].
- Draw what each figure's "description" says, using the facts in {STORY_DIR}/facts.md, {STORY_DIR}/research/research_evidence.md and plan.json. Mark examples as illustrative if they are not from the sources.
- The figure title states the point a reader should leave with (e.g. "Breadth first, then depth by risk tier"), not a label such as "dashboard" or "overview".
- When colour carries meaning (tiers, inputs vs outputs), add a legend.

Layout rules – the pipeline measures every figure after it is drawn and sends back each defect:
- Every label must fit inside its box with a margin. At fontsize 10, a box 3 units wide (on a 20-unit-wide axis, 10–12 inch figure) holds about 18 characters per line. Wrap with \n, or widen the box.
- No text may overlap other text.
- Arrows run in the gaps between boxes and start and end on box edges. They never cross a label; route a feedback loop around the boxes (below or above them), not through them.
- Keep all text inside the axes (no clipping at the edges).
- Leave at least 0.5 units between neighbouring boxes.

After writing it, run it with the project Python (e.g. `python {STORY_DIR}/figures.py`) and fix any error until all PNG files exist. Look at each PNG.
- If {STORY_DIR}/feedback.md exists, apply every point about the figures and keep the rest.
- Do not change any other file.
