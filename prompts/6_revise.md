PIPELINE STEP: revise (round {ROUND})

The critic panel scored {STORY_DIR}/content.md against the quality gates and the gold document. It did not pass yet.

Gate result: {GATE_SUMMARY}

Findings to fix, grouped by section (most severe first). Each line: [severity] defect – target – evidence → fix. Fact IDs refer to {STORY_DIR}/facts.md.

{FINDINGS}

Revise {STORY_DIR}/content.md:
- Fix every high finding and as many medium findings as you can.
- "fact_not_used": add the fact (with its exact numbers, versions, codes and caveats) where it belongs. Look it up in facts.md.
- "below_requirement_floor" / "missing_topics": add requirements for the missing topics, following {STORY_DIR}/section_briefs.md and the gold exemplar rows there.
- "merged_sections": split the section into one numbered section per topic, each with its own requirement table and ID prefix. Renumber the following sections and update the ask table and cross-references (do not edit plan.json).
- "vague"/"not_testable"/"vague_sentence": rewrite with the checkable rule, number, code or artifact.
- "internal_citation"/"internal_reference": cite the source paper [file, p.N] or the reference entry instead; References list real sources with links.
- decision findings: give at least 3 concrete options with pros and cons, one recommendation with numbered steps, questions for the team and a sign-off table.
- "standalone_figures_section": move each figure into the section it explains, refer to it in the text, and delete the Figures section.
- "unsupported_claim": use the value from facts.md or the evidence, or mark it "to be confirmed".
Keep everything that is already right. Keep requirement IDs stable (new requirements get new numbers at the end of their table). Follow the format rules in prompts/3_draft.md. Use only the sources listed there. Do not change any other file.
