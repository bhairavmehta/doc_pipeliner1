PIPELINE STEP: plan

You are preparing a requirements document for a user story. Work only inside the folder {STORY_DIR}.

Read these files:
- {STORY_DIR}/story.md – the user story (the request from the team). Treat it as the specification of what the document must cover.
- {STORY_DIR}/facts.md – the fact ledger: every finding from the research, split into numbered facts (F-001, F-002, …). Every fact must be planned into a section.
- {STORY_DIR}/research_findings.md – the research findings the ledger was built from.
- {STORY_DIR}/section_types.md – the section types the pipeline knows, what each must cover and its requirement floor.
- Any text files in {STORY_DIR}/inputs/_text/ – other supporting material (may be empty).
- The list of source papers in {STORY_DIR}/research/sources/ (file names only – do not read whole PDFs).
- {EXAMPLE} – a finished, reviewed requirements document. Its outline shows the depth expected: separate sections for inputs, outputs, source handling, reruns, review handoff, validation and acceptance, each decision, method, governance, open items and references.

Then write the file {STORY_DIR}/plan.json with exactly this structure (valid JSON, UTF-8):

{
  "story_id": "<story or work-item number from the story, e.g. 123456>",
  "doc_title": "<short document title, e.g. Order Tracking Service – Requirements>",
  "subtitle": "<e.g. User Story 123456 · Parent #123400: Order tracking>",
  "footer": "<e.g. US 123456 · Order Tracking Service Requirements>",
  "output_name": "<file name without extension, letters/digits/underscores only, e.g. US123456_Order_Tracking_Service_Requirements>",
  "asks": [ {"ask": "<one thing the story asks for, in the story's words>", "section": "<numbered section that will cover it, e.g. 3. Inputs>"} ],
  "outline": ["1. Summary", "2. ...", "..."],
  "sections": [ {"heading": "<exactly as in outline>", "type": "<a type from section_types.md, or other>", "facts": ["F-001", "F-007"], "notes": "<what this section must decide or define>"} ],
  "unused_facts": [ {"id": "F-0xx", "reason": "<why it does not belong in this document>"} ],
  "figures": [ {"file": "fig1_<short_name>.png", "caption": "Figure 1. <caption that states the point>", "section": "<heading of the section it sits in>", "description": "<what the figure shows: boxes, arrows, labels, colours, legend – enough to draw it>"} ],
  "evidence_queries": [ {"id": "Q1", "heading": "<short topic>", "question": "<what the document needs to confirm from the source papers>", "keywords": ["<10–20 search words and phrases likely to appear in the papers>"]} ]
}

Rules:
- List every ask in the story, including comments from team members (e.g. a request for a diagram, or an open question someone raised). Each ask must map to a section in the outline. A request for a visual maps to the section where the figure will sit, never to a separate "Figures" section.
- Outline: 10–16 numbered sections. Start with "1. Summary". Give each requirement topic its own section – never merge source handling, reruns and review handoff into one section. Include "Validation and acceptance" (measurable targets), a method section when the story involves a model or algorithm, and "Governance" when people must approve AI output. End with "Open items" and "References".
- Include a section marked (DECISION) in its heading for every open question or agreement the story asks for, e.g. "9. ICAO categories in scope (DECISION)".
- sections: one entry per outline item, same headings, same order. Assign every fact in facts.md to at least one section where it will be used. A fact may go to several sections. Put a fact in unused_facts only if it truly does not belong, with a reason; keep that list under 15% of the facts.
- Figures: 1–3 figures that carry the argument (e.g. the end-to-end flow with its review loop; the recommended strategy for a DECISION). Each sits in a named section.
- evidence_queries: 5–8 topics covering the facts the document will rely on (standards and versions, definitions, data sources, methods, recommendations). They are used to pull matching passages from the source papers.
- Use only information from the files above. Do not browse the web.
- Do not create or change any other file.
