PIPELINE STEP: draft section {SECTION_NO} of {SECTION_TOTAL}

Write ONE section of the requirements document into the file {STORY_DIR}/sections/{SECTION_FILE}.

The section: {SECTION_HEADING}

Its brief (type, topics it must cover, requirement floor, assigned facts, gold exemplar rows):

{SECTION_BRIEF}

Context you may read: {STORY_DIR}/story.md, {STORY_DIR}/plan.json (outline, asks, figures), {STORY_DIR}/facts.md, {STORY_DIR}/research/research_evidence.md, and the sections already written in {STORY_DIR}/sections/ (to keep IDs, terms and cross-references consistent). Quality reference: {EXAMPLE}.

Write:
- The heading line "# {SECTION_HEADING}" and then the body only (no front matter).
- If this is section 1: first the details table (User story, Parent, Owner, Status "Draft for team review – decisions needed are marked DECISION", Builds on, Date {TODAY}) ABOVE the heading, then the summary and the "What this story asked for, and where it is covered" table (Ask | Section) for every ask in plan.json.
- Every rule from prompts/3_draft.md applies: requirement tables ID | Requirement | Priority with a section prefix, the floor met, every topic covered, every assigned fact used with its exact values, citations to source papers only, figures from plan.json that belong to this section placed and referred to, DECISION structure where the heading says DECISION, and the Markdown format rules.
- Do not change any other file.
