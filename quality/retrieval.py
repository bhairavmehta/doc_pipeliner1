"""
K3 – hybrid evidence retrieval.

BM25 (the existing ranker in research_findings.py) finds passages that share words with the question.
When an embedding model is configured (SLM_EMBED_MODEL) it adds a dense ranking and fuses the two with
reciprocal rank fusion; when a reranker is configured (SLM_RERANK_MODEL) a cross-encoder reorders the
fused shortlist. Without those settings this is exactly the old BM25 behaviour.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from quality import slm  # noqa: E402

RRF_K = 60


def mode():
    return "hybrid+rerank" if slm.embed_enabled() and slm.rerank_enabled() else \
        "hybrid" if slm.embed_enabled() else "bm25+rerank" if slm.rerank_enabled() else "bm25"


def rank(all_chunks, query_terms, top, bm25_rank, question=None, per_file=3):
    """Same contract as research_findings.rank: a list of chunk dicts with a 'score'."""
    m = mode()
    if m == "bm25":
        return bm25_rank(all_chunks, query_terms, top)
    question = question or " ".join(query_terms[:1])
    wide = bm25_rank(all_chunks, query_terms, max(top * 6, 40))
    fused = {id(c): 0.0 for c in wide}
    key = {(c["file"], c["page"], c["text"][:80]): c for c in wide}
    for r, c in enumerate(wide):
        fused[id(c)] += 1 / (RRF_K + r + 1)
    pool = list(wide)
    if slm.embed_enabled():
        try:
            qv = slm.embed([question])[0]
            vecs = slm.embed([c["text"][:2000] for c in all_chunks])
            dense = sorted(range(len(all_chunks)), key=lambda i: -slm.cosine(qv, vecs[i]))[:max(top * 6, 40)]
            for r, i in enumerate(dense):
                c = all_chunks[i]
                k = (c["file"], c["page"], c["text"][:80])
                if k not in key:
                    c = dict(c, score=0.0)
                    key[k] = c
                    pool.append(c)
                    fused[id(c)] = 0.0
                fused[id(key[k])] += 1 / (RRF_K + r + 1)
        except slm.SLMError as e:
            print(f"    [retrieval] embeddings unavailable ({e}); using BM25 only")
    pool.sort(key=lambda c: -fused[id(c)])
    shortlist = pool[:max(top * 4, 24)]
    if slm.rerank_enabled():
        try:
            scores = slm.rerank(question, [c["text"][:2000] for c in shortlist])
            shortlist = [c for _, c in sorted(zip(scores, shortlist), key=lambda t: -t[0])]
        except slm.SLMError as e:
            print(f"    [retrieval] reranker unavailable ({e})")
    picked, count = [], {}
    for c in shortlist:
        if count.get(c["file"], 0) >= per_file:
            continue
        count[c["file"]] = count.get(c["file"], 0) + 1
        picked.append(dict(c, score=round(fused[id(c)] * 1000, 2)))
        if len(picked) == top:
            break
    return picked
