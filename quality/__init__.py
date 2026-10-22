"""
quality/ – the quality layer for the document pipeline.

Knowledge layer
  facts.py       K1  fact ledger: splits research_findings.md into atomic, numbered facts with key terms
  patterns.py    K2  section-pattern library: checklists, requirement floors and gold exemplars per section type
  retrieval.py   K3  hybrid evidence retrieval: BM25 + optional dense embeddings + optional reranker

Critic panel (deterministic by default; each can call a small language model through slm.py)
  critics.py     C1 requirement quality · C2 claim support · C3 coverage and fact recall ·
                 C4 specificity · C6 decision quality · citation and reference checks · ask coverage
  figure_qa.py   C5  figure QA: text collisions, clipped labels, text over arrows (runs figures.py under a probe)

Gate and evaluation
  scorecard.py   D1–D10 rubric, hard gates, score relative to a gold document, optional J1 judge
  evaluate.py    command line: score any .md or .docx against a gold document (regression suite)
  training.py    exports training data for the SLM critics (feedback flywheel)

Helpers
  slm.py         OpenAI-compatible client for local small models (vLLM, Ollama, TGI) and the judge model
  doc_model.py   parses a pipeline Markdown document into sections, requirement rows, decisions and citations
  docx_to_md.py  converts a .docx (gold or pipeline output) into the pipeline's Markdown format
"""
