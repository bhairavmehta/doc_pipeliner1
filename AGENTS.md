# AGENTS.md – document pipeline

Instructions for AI coding agents (Codex and similar) working in this folder.

## What this project is
`run_pipeline.py` turns a user-story prompt, research findings and source papers into a requirements document (Word + Markdown), figures, a QA review and a run report. Codex does the planning, writing and review; Python does setup, evidence extraction, checks and the Word build. See `README.md`.

There are two ways an agent is used here. Check which one applies before doing anything:
- The prompt starts with `PIPELINE STEP: <name>` → **Pipeline runs** below.
- Anything else (e.g. "generate the 311617 report", "run the pipeline") → **Direct requests** below.

## Pipeline runs (stories/<id>/)
`run_pipeline.py` calls `codex exec` with prompts that start with `PIPELINE STEP: <name>`. For those prompts:
- Follow the prompt exactly.
- Work only inside the story folder it names (e.g. `stories/123456/`). Read the project files it mentions; change nothing else.
- In that folder: `story.md` is the request, `research_findings.md` and `research/research_evidence.md` are the sources, `plan.json` is the plan, `content.md` is the document draft.
- Do not run `run_pipeline.py` yourself; the pipeline runs the build and the checks.

## Direct requests (no PIPELINE STEP prompt)
The inputs live in the project root, not in `stories/`. `stories/` is created by the pipeline and is not in git, so it is normally missing in a fresh clone – that is expected.

| Input | Where |
|---|---|
| User story | `<id>_story.md` in the root (e.g. `311617_story.md`) |
| Research findings | `research/research_findings.md` |
| Source papers | `research/sources/` (skip the test files `T1_*`, `T2_*`, `T3_*` and `manifest.csv`) |
| Example / gold document | `examples/gold/US311617/US311617_benchmark.md` (default) |

The story id is the first 5–8 digit number in the story file. The output folder is `stories/<id>/`.

1. **Set up** (once): `py -m venv .venv` then `.venv\Scripts\python.exe -m pip install -r requirements.txt` (Linux/macOS: `python3 -m venv .venv` and `.venv/bin/python`).
2. **If the `codex` CLI is available** (`codex --version` works): run
   `.venv\Scripts\python.exe run_pipeline.py --story 311617_story.md --research research/research_findings.md --sources research/sources`
   and report the result.
3. **If `codex` is not available** (for example inside a Codex cloud task), do the Codex steps yourself:
   1. `run_pipeline.py --story … --research … --sources … --dry-run` – runs setup and saves the prompts to `stories/<id>/_prompts/`.
   2. Write `stories/<id>/plan.json` following `_prompts/plan.md` (facts are in `stories/<id>/facts.md`). Then `run_pipeline.py --id <id> --only plan --validate-only` checks it and writes `section_briefs.md`; fix what it reports.
   3. `run_pipeline.py --id <id> --only evidence` – builds `research/research_evidence.md`.
   4. Write `stories/<id>/figures.py` following `_prompts/figures.md`, then run `python quality/figure_qa.py stories/<id>/figures.py` and fix every defect it lists; look at the PNGs.
   5. Write `stories/<id>/content.md` following `_prompts/draft.md` and `stories/<id>/section_briefs.md`.
   6. Score it: `run_pipeline.py --id <id> --only critique --validate-only` writes `critique_report.md`. Fix the findings (as `_prompts/revise_template.md` describes) and score again, until the gate passes or two rounds are done.
   7. `run_pipeline.py --id <id> --only build` – builds the `.docx` and `.md`. Fix any reported problem in `content.md` and build again.
   8. Write `stories/<id>/qa_report.md` following `_prompts/qa.md`, then `run_pipeline.py --id <id> --only report`.
4. **Finish** by naming the output file (`stories/<id>/<output_name>.docx`) and listing what still needs a human check (items marked "to be confirmed", QA issues).

If the story, findings or sources are missing, say which file is missing and stop – do not invent a story name or folder.

## Files
| File | Role | Edit? |
|---|---|---|
| `run_pipeline.py` | The pipeline | Only when asked; test after |
| `prompts/` | Prompts the pipeline sends to Codex (`1_plan`, `2_figures`, `3_draft`, `4_fix`, `5_qa`, `6_revise`, `7_judge`, `8_section_draft`) | Only when asked |
| `quality/` | Quality layer: fact ledger, section patterns, critics, figure QA, scorecard, evaluation, training export | Only when asked; test with `quality/evaluate.py` after |
| `quality/gates.json`, `quality/patterns/section_patterns.json` | Gate thresholds and section checklists | Only when asked |
| `generate_doc.py`, `md_to_content.py`, `research_findings.py` | Word build, Markdown reader, evidence extraction | Only when asked; test after |
| `figure_style.py` | Figure style reference (colours, boxes, arrows) | No |
| `examples/` | Gold documents (quality reference and scoring benchmark) and a sample story | No |
| `<id>_story.md`, `research/` | Inputs for direct requests | Only when asked |
| `research/sources/`, `stories/<id>/research/sources/` | Source papers | Never edit or delete |
| `.env` | Private settings | Never read aloud, copy, print or commit |

## Rules
- **Facts:** use only the files provided for the story (story, research findings, evidence, source papers, inputs). No facts from memory. Mark anything unconfirmed as "to be confirmed". Cite papers as `[file name, p.N]`.
- **Format:** follow the Markdown rules in `prompts/3_draft.md` exactly.
- **Language:** plain, simple English; short sentences.
- **Data safety:** only documents approved for this tool belong here. Never put other data into prompts, files or web searches.
- **Web access:** do not browse the web unless the user explicitly asks and it is allowed.
- **Tokens:** do not read whole PDFs; use `research/research_evidence.md` or grep the extracted text in `research/sources/_text/`.
