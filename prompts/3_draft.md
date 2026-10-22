PIPELINE STEP: draft

Write the requirements document as Markdown into the file {STORY_DIR}/content.md.

Revision mode: if {STORY_DIR}/feedback.md exists and {STORY_DIR}/content.md already exists, revise content.md instead of starting again: apply every point in feedback.md, keep everything else as it is, and keep requirement IDs stable.

Sources (use only these – do not add facts from memory, do not browse the web):
- {STORY_DIR}/story.md – the user story: what the document must cover.
- {STORY_DIR}/section_briefs.md – THE BRIEF FOR EACH SECTION: its type, the topics it must cover, its requirement floor, the facts assigned to it (full text, with IDs) and gold exemplar rows. Write each section to its brief.
- {STORY_DIR}/facts.md – the full fact ledger and the key sources (with links) for References.
- {STORY_DIR}/plan.json – title, subtitle, footer, outline, asks and figures to use.
- {STORY_DIR}/research/research_evidence.md – passages from the source papers, each with its citation [file, p.N]. Use it to confirm facts and to cite sources.
- Text files in {STORY_DIR}/inputs/_text/ (may be empty).
- If you need a detail that is not in the evidence, search the extracted text in {STORY_DIR}/research/sources/_text/ (one JSON file per paper: a list of [page, text]) with grep. Do not read whole PDFs.

Quality reference:
- {EXAMPLE} is a finished, reviewed requirements document. Match its structure, depth, table style, level of detail and plain-English tone: requirements that name the rule, the number, the code or the artifact a reviewer can check. Do not copy its content unless the same point genuinely applies to this story and is supported by the sources above.

Content:
- Front matter with title, subtitle and footer from plan.json.
- A details table first: User story, Parent, Owner (if given; otherwise "to be confirmed"), Status ("Draft for team review – decisions needed are marked DECISION"), Builds on, Date ({TODAY}).
- "1. Summary": 2 paragraphs (what the system does, who decides, where the result is used; what this document defines and which decisions it asks for), then a table "What this story asked for, and where it is covered" (columns Ask | Section) listing every ask in plan.json.
- Follow the outline and the section briefs. Write requirements as tables with columns ID | Requirement | Priority (Must/Should), with a short ID prefix per section (e.g. "Inputs" → IN-1, "Source handling" → SRC-1, "Rerun behavior" → RR-1). Keep IDs unique. Start each requirement with a 1–3 word label, then the checkable rule (e.g. "Snapshots. Each run uses a dated snapshot of each source with a cut-off date and checksum so it can be repeated exactly.").
- Meet each section's requirement floor and cover every topic in its brief. Never write a requirement that only names a topic ("handle reruns", "maintain versioning").
- Use every fact assigned to a section. Keep its exact numbers, versions, codes and names, and keep its caveats.
- Every open question in the story gets a section marked (DECISION) with: the question (who asked, when); a table of at least 3 concrete options (Option | Pros | Cons) that name the actual members, codes or numbers involved; one recommendation with numbered steps and any stopping rule or criteria; "Questions for the team"; and a sign-off table (Team member | Agree? (Y / N) | Comments) with 4 empty rows.
- Add a "Validation and acceptance" table (Check | Rule | Proposed target) with numeric targets, labelled as proposals for the team to confirm.
- Place each figure from plan.json once, inside the section named in plan.json, with its caption, and refer to it in the text ("Figure 1 shows …"). Never put figures in their own section.
- Citations: where a requirement or recommendation rests on a source paper, cite it as [paper_file_name.pdf, p.12] using the exact file name in research/sources. Never cite research_findings.md, research_evidence.md, plan.json or "Research findings, Section N" – cite the underlying source instead. Anything not confirmed by the findings or the papers is marked "to be confirmed".
- End with "Open items" (Item | Owner | Needed by; at least 4 rows; name the owner role) and "References": bullets for every key source in facts.md (title and link) and every source paper cited in the text, then a caveat note on what could not be confirmed.
- Plain, simple English. Short sentences. Tables instead of long paragraphs.

Format (the file is converted automatically – follow exactly):
---
title: <title>
subtitle: <subtitle>
footer: <footer>
---

# 1. Section heading
## Sub-heading
Normal paragraph text.
> Grey note text (for small notes and caveats)
- Bullet item
| ID | Requirement | Priority |
|---|---|---|
| **IN-1** | Requirement text | Must |
![Figure 1. Caption](fig1_name.png)

Rules:
- Start with the front matter block exactly as shown.
- Number the sections (# 1., # 2., …). Use ## for sub-headings only.
- Pipe tables need the |---| line under the header. Bold every first-column cell (**IN-1**) when it is an ID or a label. No line breaks inside table cells.
- No bold or italics inside paragraphs, no nested lists.
- Use only the figure file names listed in plan.json.
- Do not change any file other than {STORY_DIR}/content.md.
