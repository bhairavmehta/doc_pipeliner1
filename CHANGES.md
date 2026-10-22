# Changes – quality layer (October 2026)

Goal: bring pipeline output up to the reviewed US311617 benchmark. The earlier output (newdoc.docx) used about 16% of the facts in research_findings.md, had 7 requirements against the benchmark's 45, and cited the pipeline's own working files. The old checks only looked at format, so none of that was caught.

## Results on the US311617 material (`quality/evaluate.py`, rules mode)

| Document | Gate | vs gold | Fact recall | Requirements | Depth (D4) | Req quality (D5) | Decisions (D7) | Citations (D8) | High findings |
|---|---|---|---|---|---|---|---|---|---|
| Benchmark (gold) | PASS | 100% | 86% | 45 | 0.99 | 0.99 | 1.0 | 0.90 | 0 |
| newdoc.docx (old pipeline) | FAIL | 42% | 16% | 7 | 0.28 | 0.67 | 0.0 | 0.0 | 40 |

## Phase 0 – no new models
- **Gold example by default.** `examples/gold/US311617/US311617_benchmark.md` (converted from the reviewed .docx with the new `quality/docx_to_md.py`) replaces the short fictional example as `--example`, and is the scoring reference (`--gold`).
- **Plan carries facts and section types.** `plan.json` now has `sections` (type + assigned fact IDs per outline item) and `unused_facts`. The pipeline rejects plans with unassigned facts, merged sections ("Sources, reruns and handoff"), figures-only sections, or no DECISION section for an open question.
- **Section briefs.** After the plan, `section_briefs.md` gives the writer, per section: checklist topics, requirement floor, assigned facts with full text, and gold exemplar rows.
- **Draft prompt** requires requirement floors, every assigned fact with exact values, ≥ 3 concrete options per DECISION with a stepwise recommendation, a validation table with targets, figures inside the sections they explain, citations to source papers only, and References with links.
- **Figure layout check.** `figures.py` now runs under a probe (`quality/figure_qa.py`) that measures overlapping labels, labels wider than their box, arrows through text and clipped text; defects go back to Codex.
- **Blocking QA.** High QA issues get one fix round, a re-score and a rebuild (`--no-qa-fix` to keep QA advisory). The QA prompt now focuses on what rules cannot check.
- **Bug fixes.** Fix prompts pointed at `prompts/pipeline/…` (a path that does not exist); now `prompts/…`.

## Phases 1–2 – knowledge layer and critic panel
- **K1 fact ledger** (`quality/facts.py`, new `facts` step): numbered facts with distinctive key terms; recall ignores terms already in the story.
- **K2 section-pattern library** (`quality/patterns/section_patterns.json` curated; `exemplars.json` mined from gold with `python quality/patterns.py mine`).
- **K3 hybrid retrieval** (`quality/retrieval.py`): BM25, plus dense embeddings fused by reciprocal rank and a cross-encoder reranker when `SLM_EMBED_MODEL` / `SLM_RERANK_MODEL` are set.
- **Critic panel** (`quality/critics.py`): C1 requirement quality, C2 claim support, C3 coverage/floors/fact recall/ask coverage, C4 specificity, C6 decisions, C7 citations, C8 structure, plus C5 figures. Rules by default; `--critic-mode hybrid` adds a small model for C1 and C2 through any OpenAI-compatible server (`quality/slm.py`, temperature 0, cached).
- **New `critique` step**: scorecard D1–D10, hard gates (`quality/gates.json`), score relative to gold, and up to `--revise-rounds` targeted revisions (`prompts/6_revise.md`) with findings grouped by section.
- **J1 judge** (`--judge`): pairwise per dimension against the gold document, both orders, Platt calibration from `quality/calibration.json` when present.
- **Section-by-section drafting** (`--draft-mode sections`, `prompts/8_section_draft.md`).

## Phase 3 – flywheel and regression suite
- `content.generated.md` is saved after critique; human edits to `content.md` become training pairs.
- `quality/training.py export` writes C1/C4 labelled data, preference pairs (DPO / reward model) and chat-format SFT data for a QLoRA fine-tune of the C1 critic. Synthetic negatives are made from gold rows.
- `quality/evaluate.py` scores any .md/.docx, writes CSV/JSON, and exits 3 on a regression against a saved baseline.

## Compatibility
- No new required packages (still python-docx, matplotlib, pypdf). Models are optional and configured in `.env` (see `.env.example`).
- New steps: `check, setup, facts, plan, evidence, figures, draft, critique, build, qa, report`. Existing story folders: re-run `--from facts`.
- By default the run does not stop when gates fail after revision; the run report shows the scorecard. Use `--strict-gates` to stop.

## Tested here
- Full run end to end with a stand-in for `codex exec`. It exercised the plan fix loop, a figure-defect fix loop, the format fix loop, critique → revise (51% → 100% of gold), the blocking QA fix and rebuild, and the run report.
- Hybrid mode (C1/C2 SLM calls, embeddings + reranker, J1 judge, SLM fact splitting) against a mock OpenAI-compatible server.
- Dry run on the fictional sample story (no sources, different domain).
- Not tested here: real Codex, real small models, a fine-tune. The thresholds in `gates.json` are proposals to calibrate on your first gold documents.
