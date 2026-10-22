PIPELINE STEP: qa

Review the requirements document as a careful, skeptical {REVIEWER}. Do not change any files.

Read:
- {STORY_DIR}/content.md – the document to review.
- {STORY_DIR}/story.md – what the document had to cover.
- {STORY_DIR}/facts.md – the facts it should be based on (and research_findings.md behind them).
- {STORY_DIR}/research/research_evidence.md – passages from the source papers with citations. To check a citation that is not in the evidence, grep the extracted text in {STORY_DIR}/research/sources/_text/. Do not read whole PDFs.
- {STORY_DIR}/critique_report.md – what the automatic critics already measured (fact recall, requirement quality, coverage, citations, figures). Do not repeat those findings; spend your review on what rules cannot see.

Check:
1. Every fact, number, version and category code in content.md against facts.md and the source papers. Flag anything not supported or misread, and any citation [file, p.N] whose page does not say what the sentence claims.
2. Reasoning: requirements that contradict each other, a recommendation that does not follow from its pros and cons, targets that conflict, steps in the wrong order.
3. Domain errors a {REVIEWER} would catch: a wrong definition, a misapplied standard, a missing safety or governance control.
4. Every ask in story.md is covered by a section, and open items have a named owner.

Use High only for issues that would mislead a reader or block approval.

Reply with Markdown only, in this layout:

## QA summary
<2–4 sentences: overall quality, number of issues by severity>

## Issues
| # | Severity (High/Medium/Low) | Location | Issue | Suggested fix |
|---|---|---|---|---|

## Coverage of the story
| Ask | Covered in | OK? |
|---|---|---|
