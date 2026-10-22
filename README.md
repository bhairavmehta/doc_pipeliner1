# Document Pipeline: User Story → Requirements Document (with Codex)

`run_pipeline.py` turns a user-story prompt into a finished requirements document (Word + Markdown), its figures, a QA review and a run report. It uses **Codex** (`codex exec`) for the writing and judgment steps and the Python scripts in this folder for everything else. It works for any user story that asks for a requirements-style document, on any topic.

```
story.md + research_findings.md + source papers (+ example document, + other inputs)
        │
        ▼
python run_pipeline.py --story … --research … --sources …
        │
        ▼
stories/<id>/<Document>.docx   +   critique_report.md   +   qa_report.md   +   run_report.docx
```

**What changed in this version (quality layer).** A draft no longer goes straight from Codex to Word. The findings are split into a numbered fact ledger; the plan assigns every fact and gives every section a type with a checklist and a requirement floor; a critic panel (rules, optionally small language models) scores the draft on ten dimensions against a gold document; drafts that fail the hard gates go back for targeted revision; figures are measured for overlapping labels; and High QA issues get a fix round. See section 11 and `CHANGES.md`.

---

## 1. What you need to provide

### Required

| # | Input | Format | What it is | How to pass it |
|---|---|---|---|---|
| 1 | **User story prompt** | `.md` or `.txt` | The story exactly as you received it: number, parent, asks, evidence required, team comments and open questions. The pipeline treats this as the specification. | `--story story.md` |
| 2 | **Research findings** | `research_findings.md` | Your research summary: numbered sections of findings, caveats and key sources with links. The document's facts come from here. | `--research research_findings.md` |

### Strongly recommended

| # | Input | Format | What it is | How to pass it |
|---|---|---|---|---|
| 3 | **Source papers** | Folder of `.pdf`, `.html`, `.txt` | The documents behind the research (standards, reports, papers, web pages saved as HTML). The pipeline extracts the relevant passages so Codex can check facts and cite `[file, p.N]` without reading whole PDFs. Name files clearly, e.g. `03_Standard_X_v2.pdf`. | `--sources path/to/papers` |
| 4 | **Example / gold document** | `.md` (convert a .docx with `python quality/docx_to_md.py`) | A finished, reviewed requirements document. Codex matches its structure, depth and tone, and the critic panel scores the draft against it. The default is the reviewed US311617 document in `examples/gold/US311617/`. Add more gold documents to `examples/gold/` and run `python quality/patterns.py mine`. | default, or `--example my_best_doc.md --gold my_best_doc.md` |

### Optional

| # | Input | Format | What it is | How to pass it |
|---|---|---|---|---|
| 5 | **Other supporting files** | Folder of `.md`, `.txt`, `.docx`, `.pdf` | Earlier deliverables the story builds on, e.g. previous reviews, surveys or designs. Converted to text automatically. | `--inputs path/to/folder` |
| 6 | **Reviewer feedback** | `feedback.md` in the story folder | Comments after a review round. Codex revises the existing draft instead of starting again. | Save as `stories/<id>/feedback.md`, run `--from draft` |
| 7 | **Codex model / options** | text | Extra arguments for every Codex call, e.g. a specific model. | `--codex-args "-m <model>"` or env `CODEX_ARGS` |
| 8 | **Story id** | text | Only if the story text has no 5–8 digit number. | `--id 123456` |
| 9 | **QA reviewer** | text | Who the QA step reviews as, e.g. "data platform architect". Default: a subject-matter expert for the story's topic. | `--reviewer "…"` or env `QA_REVIEWER` |

> A fictional sample story with research findings and two small source files is in `examples/sample_story/` – use it for a first test.

---

## 2. One-time setup (company computer)

1. **Approval** – confirm Codex is approved for this work and for the data you will give it (public papers, team documents).
2. **Python 3.9+** from the company software catalog.
3. **Project folder** – unzip `doc_pipeline.zip`, open the folder in VS Code (or a terminal).
4. **Packages** – VS Code: *Terminal → Run Task… → "Setup: create environment and install packages"*, or:
   ```
   py -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
   (Add `--index-url https://<internal-mirror>/simple` if IT requires the company package mirror.)
5. **Codex CLI** – install it as your company instructs, then run `codex` once in a terminal to sign in. Check with `codex --version`.
   If `codex` is not on PATH, set `CODEX_BIN` to its full path (Windows: usually `...\npm\codex.cmd`).
6. **Test without using Codex** (writes the prompts only, costs nothing):
   ```
   python run_pipeline.py --story examples/sample_story/story.md --research examples/sample_story/research_findings.md --dry-run
   ```
   Open `stories/123456/_prompts/` to see exactly what Codex will be asked.

---

## 3. Running it

### A new document
```
python run_pipeline.py --story my_story.md --research research_findings.md --sources papers/ --inputs earlier_docs/
```
VS Code: *Terminal → Run Task… → "Pipeline: run"* (asks for the paths).

### Sample story (fictional)
```
python run_pipeline.py --story examples/sample_story/story.md --research examples/sample_story/research_findings.md --sources examples/sample_story/sources
```

### Re-run part of it
| Goal | Command |
|---|---|
| Continue after a failure | `python run_pipeline.py --id 123456 --from <failed step>` (the message prints the exact command) |
| Redo the text after editing plan.json | `--id 123456 --from draft` |
| Apply reviewer feedback | save `stories/123456/feedback.md`, then `--id 123456 --from draft` |
| Rebuild Word after editing content.md by hand | `--id 123456 --from build` |
| Run only the QA review | `--id 123456 --only qa` |

Steps run in this order: `check, setup, facts, plan, evidence, figures, draft, critique, build, qa, report`.

| Quality option | Effect |
|---|---|
| `--draft-mode sections` | One Codex call per section, each with its own brief (better depth, more tokens). Default `whole`. |
| `--revise-rounds N` | Critique → revise rounds when the gate fails (default 2). |
| `--strict-gates` | Stop the run if hard gates still fail after revision (default: continue and report). |
| `--critic-mode hybrid` | Add small-model critics (needs `SLM_*` settings, see `.env.example`). |
| `--judge` | Add the J1 pairwise judge against the gold document (needs `JUDGE_*` or `LLM_*`). |
| `--no-qa-fix` | Keep QA advisory (default: High QA issues get one fix round, then the document is rebuilt). |

---

## 4. What each step does

| Step | Who | What happens | Output |
|---|---|---|---|
| **check** | Python | Confirms the Python packages and the Codex CLI are available. | – |
| **setup** | Python | Creates `stories/<id>/`; copies the story, research findings, source papers, example, gold document and inputs; converts inputs (docx/pdf/html) to text; writes the section-type checklists. | `story.md`, `research_findings.md`, `research/sources/`, `inputs/_text/`, `example_requirements.md`, `gold.md`, `section_types.md` |
| **facts** | Python (K1) | Splits the findings into atomic, numbered facts (F-001 …) with the key terms that prove a fact was used; collects the key sources. Optional: a small model splits long bullets. | `facts.jsonl`, `facts.md`, `sources.json` |
| **plan** | Codex | Reads the story, facts and section types; writes the plan: every ask mapped to a section, outline, a type per section, every fact assigned to a section (or listed unused with a reason), figures placed in sections, evidence topics. The pipeline rejects merged sections, figures-only sections, unassigned facts and a missing DECISION section, and asks Codex to fix them. Then it writes a brief per section (checklist, floor, assigned facts, gold exemplar rows). | `plan.json`, `section_briefs.md` |
| **evidence** | Python | Turns the evidence topics into search queries; extracts text from every paper; ranks passages (BM25) and writes the best ones with `[file, p.N]` citations. No AI. | `research/research_evidence.md`, `research/questions.json` |
| **figures** | Codex + Python (C5) | Codex writes `figures.py`; the pipeline runs it under a probe that measures overlapping labels, labels wider than their boxes, arrows through text and clipped text, and sends every defect back (up to 2 rounds). | `figures.py`, `fig*.png`, `figure_qa.json` |
| **draft** | Codex + Python | Codex writes `content.md` from the section briefs, facts, evidence, plan and gold example (`--draft-mode sections`: one call per section). The pipeline checks the format and sends problems back (up to 2 rounds). | `content.md`, `content.json` |
| **critique** | Python [+ SLM] | The critic panel scores the draft: requirement quality, claim support, checklist coverage and requirement floors, fact recall, specificity, decisions, citations, structure, figures. Hard gates failing → Codex revises the flagged sections with the findings (up to `--revise-rounds`). Saves `content.generated.md` for the feedback flywheel. | `scorecard.json`, `findings.jsonl`, `critique_report.md` |
| **build** | Python | Builds the Word and Markdown documents (US Letter, Calibri, navy tables, page numbers). | `<output_name>.docx`, `.md` |
| **qa** | Codex | A skeptical review by the `--reviewer` role, focused on what the critics cannot see (reasoning, contradictions, domain errors, citation meaning). High issues get one fix round, a re-score and a rebuild (`--no-qa-fix` to skip). | `qa_report.md` |
| **report** | Python | Summarises the run: steps, timings, files, Codex tokens, story coverage, items marked "to be confirmed", QA issues, the quality scorecard, next steps. | `run_report.md`, `run_report.docx` |

### Everything in `stories/<id>/` after a run
```
story.md, research_findings.md, example_requirements.md, gold.md   inputs (copies)
facts.jsonl, facts.md, sources.json                        fact ledger (K1)
section_types.md, section_briefs.md                        section checklists and per-section briefs (K2)
inputs/ , inputs/_text/                                    supporting files and their text
research/sources/ , research/sources/_text/                source papers and extracted text (cached)
research/questions.json , research/research_evidence.md    evidence topics and cited passages
plan.json                                                  document plan
figures.py , fig*.png                                      figures
content.md , content.json                                  document text
content.generated.md                                       the pipeline's final text, before any human edit (flywheel)
scorecard.json , findings.jsonl , critique_report.md       quality scorecard D1–D10 and critic findings
figure_qa.json                                             measured figure defects
sections/                                                  per-section drafts (--draft-mode sections)
<output_name>.docx , <output_name>.md                      THE REQUIREMENTS DOCUMENT
qa_report.md                                               QA review
run_report.md , run_report.docx                            RUN REPORT
run_state.json                                             step status (used for --from / resume)
_prompts/                                                  exact prompts sent to Codex (for audit / manual use)
logs/                                                      Codex event logs and messages per step
```

---

## 5. How good will the document be?

**Structure and format: consistent.** The prompts, the Markdown rules, the automatic checks and the example document fix the layout: details table, ask-to-section map, requirement tables with IDs and Must/Should, decision sections with options and a recommendation, sign-off tables, figures, open items, references, and the same Word styling.

**Content: close, but not identical – plan on a review round.** Why:

| Factor | Effect | What you can do |
|---|---|---|
| Quality of `research_findings.md` | The document's facts come from it. Gaps here become "to be confirmed" or thin sections. | Give complete, specific findings with sources. |
| Source papers provided | With papers, Codex can check and cite facts; without them it relies on the findings only. | Provide the papers in `--sources`. |
| Example document | Sets depth and style. The included example is short and fictional. | Use your best recent reviewed document with `--example`. |
| Codex model | Stronger models write better requirements and figures. | Use the strongest model your company approves (`--codex-args "-m …"`). |
| One pass vs. iteration | Hand-made documents usually go through several review rounds; the pipeline does one draft + automatic fixes + QA. | Use `feedback.md` + `--from draft` for a second round. |
| Figures | Codex draws them in code; the pipeline checks they exist, not how they look. | Open the PNGs; ask for changes via `feedback.md` or edit `figures.py`. |
| Variation between runs | Wording differs from run to run. | Keep the approved version; re-run only the steps you need. |

Expect a strong first draft that needs **about 30–60 minutes of review**: read the Word file, work through `qa_report.md` (High issues first) and the "to be confirmed" list in `run_report.docx`, then either edit `content.md` and run `--from build`, or write `feedback.md` and run `--from draft`.

---

## 6. Cost and time

| Step | Approx. Codex tokens |
|---|---|
| plan | 20,000–50,000 |
| figures | 20,000–60,000 |
| draft (+ fixes) | 40,000–120,000 |
| qa | 20,000–60,000 |
| **Total per run** | **about 100,000–300,000** |

The real numbers are in `run_report.docx` (summed from Codex's own usage reports, when Codex provides them). Re-running a single step (`--only`, `--from`) costs only that step. Typical run time: 10–30 minutes, depending on the model.

---

## 7. Data protection and control

- Codex runs with `--sandbox workspace-write` inside this folder (it can edit files there and run commands like `python figures.py`), and **read-only** for the QA review.
- Every prompt says which files Codex may change, and `AGENTS.md` repeats the rules (use only the provided sources, no web browsing, mark unconfirmed facts, never touch `.env`).
- Every prompt sent is saved in `_prompts/` and every Codex event in `logs/`, so the run can be audited.
- Give Codex only public papers and documents approved for that tool.
- The output is a draft. A person reviews and approves it before it is published.

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `Codex CLI not found` | Install Codex, run `codex` once to sign in, or set `CODEX_BIN` to its full path. |
| `codex exec failed … not signed in` / 401 | Run `codex` in a terminal and sign in again. |
| `codex exec failed … unknown option` | Your Codex version uses different flags. Run `codex exec --help` and adjust the `cmd = [...]` line in `Run.codex()` in `run_pipeline.py`. |
| Codex did not finish in time | Set `CODEX_TIMEOUT=3600` (seconds) and run `--from <step>`. |
| `plan.json still invalid` / `content.md still has problems` | Open the file, fix the listed problem by hand, then `--from evidence` or `--from build`. |
| `Python package … missing` | Run the setup task / `pip install -r requirements.txt`. |
| Evidence says "No source papers" | Pass `--sources` with a folder of PDF/HTML/TXT files, then `--from evidence`. |
| A figure looks wrong | Edit `stories/<id>/figures.py`, run `python stories/<id>/figures.py`, then `--from build`; or describe the change in `feedback.md` and run `--from figures`. |
| Want to use another AI tool instead | Run with `--dry-run`, paste the prompts from `_prompts/` into that tool in order (plan → figures → draft → qa), save its files into the story folder, then `--from build`. |

---

## 9. Files in this folder

| File / folder | What it is |
|---|---|
| `run_pipeline.py` | The pipeline |
| `prompts/` | The five prompts sent to Codex: `1_plan`, `2_figures`, `3_draft`, `4_fix`, `5_qa` (editable) |
| `generate_doc.py` | Builds the Word and Markdown documents |
| `md_to_content.py` | Reads and checks the Markdown draft |
| `research_findings.py` | Extracts cited passages from the source papers (BM25, or hybrid BM25 + embeddings + reranker when configured; also has an optional AI mode, see its header) |
| `quality/` | The quality layer: fact ledger, section patterns, critics, figure QA, scorecard and gates, evaluation, training export, SLM client (see section 11) |
| `examples/gold/` | Reviewed gold documents: the default example and the scoring reference |
| `.env.example` | Optional settings for small models and the judge |
| `figure_style.py` | Figure style reference for Codex; `python figure_style.py` draws a sample |
| `examples/example_requirements.md` | Fictional example document (quality and style reference) |
| `examples/sample_story/` | Fictional story, research findings and sources for a first test |
| `AGENTS.md` | Rules Codex reads automatically |
| `requirements.txt` | Python packages |
| `.vscode/` | Tasks (Ctrl+Shift+B = "Pipeline: run"), Run and Debug entries, settings |
| `stories/` | Created by the pipeline: one folder per story |

## 10. Scope and limits

- Produces **requirements-style documents** (requirement tables with IDs and Must/Should, decision sections, sign-off tables). For another kind of deliverable (reference summary, report, memo), change `prompts/3_draft.md` and give a matching `--example`.
- Codex does not browse the web in this pipeline; facts come only from your research findings, papers and inputs.
- The output is a draft for human review and approval.

---

## 11. Quality layer (`quality/`)

The pipeline used to check only format. It now measures content against a gold document and sends weak drafts back.

```
facts (K1) ──► plan + section briefs (K2) ──► draft ──► critic panel ──► gate ──► build ──► QA (blocking) ──► report
                                                 ▲                         │ fail
                                                 └──── targeted revise ◄───┘   (max --revise-rounds)
```

| Part | File | What it does | Model |
|---|---|---|---|
| K1 fact ledger | `quality/facts.py` | Numbered facts with key terms; recall check | rules; optional SLM split |
| K2 section patterns | `quality/patterns.py`, `quality/patterns/` | Checklists, requirement floors, gold exemplar rows per section type | curated + mined from gold |
| K3 retrieval | `quality/retrieval.py` | BM25, plus dense embeddings and a reranker when configured | optional embedding + reranker |
| C1 requirement quality | `quality/critics.py` | Testable, specific, atomic, not vague, not duplicated | rules; optional SLM (hybrid) |
| C2 claim support | `quality/critics.py` | Numbers, versions, codes must come from facts, evidence, story or papers | rules; optional SLM verifier |
| C3 coverage | `quality/critics.py` | Checklist topics, requirement floors, merged sections, fact recall, ask coverage | rules |
| C4 specificity | `quality/critics.py` | Specifics per 100 words vs gold; vague sentences with suggested facts | rules |
| C5 figure QA | `quality/figure_qa.py` | Label overlaps, overflow, arrows through text, clipping | measured; optional VLM |
| C6 decisions | `quality/critics.py` | ≥ 3 concrete options, pros/cons, stepwise recommendation, sign-off | rules |
| C7/C8 citations, structure | `quality/critics.py` | No pipeline files cited, citations resolve, key sources referenced; no figures-only section | rules |
| Gate + J1 | `quality/scorecard.py`, `quality/gates.json` | D1–D10, hard gates, score vs gold, optional pairwise judge with Platt calibration | optional frontier judge |
| Regression suite | `quality/evaluate.py` | Score any .md/.docx; compare runs; fail on regressions | – |
| Flywheel | `quality/training.py` | Training data for the critics from gold, drafts and human edits | – |

**Score any document** (e.g. an older pipeline output) against the gold document:
```
python quality/evaluate.py newdoc.docx --findings research/research_findings.md --story 311617_story.md --sources research/sources --report scorecard.md
```
On the US311617 material the gold document passes every hard gate (fact recall 86%, 45 requirements, 0 high findings); the earlier pipeline output newdoc.docx fails four (fact recall 16%, depth, decisions, citations) and scores 42% of gold.

**Small models (optional).** Run any OpenAI-compatible server in the approved environment (vLLM, Ollama, TGI) and set `SLM_BASE_URL` and `SLM_MODEL` (see `.env.example`), then use `--critic-mode hybrid`. Every call runs at temperature 0 and is cached in `.cache/slm/`, so scores repeat exactly. Without these settings every critic runs on rules alone.

**Training the critics.** After people edit `content.md`, run `python quality/training.py export`. It writes requirement rows with labels, specific-vs-vague sentences, preference pairs (human edit vs generated) and chat-format SFT data for a QLoRA fine-tune of the C1 critic. Add every approved document to `examples/gold/` and run `python quality/patterns.py mine` to refresh the exemplars.

**Tuning the gates.** Thresholds live in `quality/gates.json`. They are proposals: calibrate them on your first five gold documents, and fit `quality/calibration.json` (`{"a": …, "b": …}`) for the judge once SMEs have scored a few documents.

