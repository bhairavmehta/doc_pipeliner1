"""
Client for the small language models (critics, fact splitting, embeddings, reranking) and the judge model.

Every call runs at temperature 0, and every response is cached on disk (.cache/slm/), so a rerun with the
same inputs gives the same scores. That is the same rule the documents ask of their own pipelines.

Small models – any OpenAI-compatible server inside the approved environment (vLLM, Ollama, TGI, LM Studio):
    SLM_BASE_URL       e.g. http://localhost:8000/v1   (Ollama: http://localhost:11434/v1)
    SLM_MODEL          chat model for critics, e.g. a fine-tuned Qwen3-8B / Phi-4-mini / Llama-3.2-3B
    SLM_API_KEY        optional
    SLM_EMBED_MODEL    optional embedding model for K3 hybrid retrieval and similarity (e.g. bge-m3)
    SLM_RERANK_MODEL   optional cross-encoder for K3 (e.g. bge-reranker-v2-m3; server must expose /rerank)

Judge model (J1) – frontier model used for the holistic, pairwise judgment:
    JUDGE_PROVIDER / JUDGE_BASE_URL / JUDGE_API_KEY / JUDGE_MODEL  (openai | azure | anthropic)
    Falls back to the LLM_* settings that research_findings.py already uses.

Nothing is sent anywhere unless these variables are set; without them every critic runs in rule mode.
"""
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(os.environ.get("SLM_CACHE", ROOT / ".cache" / "slm"))


class SLMError(Exception):
    pass


def load_env():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


load_env()


def _cfg(profile):
    if profile == "slm":
        return {"provider": "openai", "base": os.environ.get("SLM_BASE_URL", ""), "key": os.environ.get("SLM_API_KEY", ""),
                "model": os.environ.get("SLM_MODEL", "")}
    if profile == "judge":
        g = lambda k: os.environ.get("JUDGE_" + k) or os.environ.get("LLM_" + k, "")  # noqa: E731
        return {"provider": (g("PROVIDER") or "openai").lower(), "base": g("BASE_URL") or "https://api.openai.com/v1",
                "key": g("API_KEY"), "model": g("MODEL"), "api_version": g("API_VERSION") or "2024-06-01"}
    raise ValueError(profile)


def enabled(profile="slm"):
    c = _cfg(profile)
    if profile == "slm":
        return bool(c["base"] and c["model"])
    return bool(c["key"] and c["model"])


def embed_enabled():
    return bool(os.environ.get("SLM_BASE_URL") and os.environ.get("SLM_EMBED_MODEL"))


def rerank_enabled():
    return bool(os.environ.get("SLM_BASE_URL") and os.environ.get("SLM_RERANK_MODEL"))


def _ssl():
    try:
        import ssl
        import truststore  # optional: company certificate store
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return None


def _post(url, body, headers, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={**headers, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl()) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SLMError(f"{url} returned HTTP {e.code}: {e.read()[:300]!r}")
    except Exception as e:  # noqa: BLE001
        raise SLMError(f"could not reach {url}: {e}")


def _cached(kind, payload, fn):
    CACHE.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((kind + "|" + json.dumps(payload, sort_keys=True)).encode()).hexdigest()
    f = CACHE / f"{key}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    out = fn()
    f.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def chat(system, user, profile="slm", max_tokens=800, json_mode=True):
    """Return the model's text (temperature 0, cached)."""
    c = _cfg(profile)
    if not enabled(profile):
        raise SLMError(f"{profile} model not configured")
    payload = {"p": c["provider"], "m": c["model"], "s": system, "u": user, "t": max_tokens, "j": json_mode}

    def call():
        if c["provider"] == "anthropic":
            data = _post(c["base"].rstrip("/") + "/v1/messages",
                         {"model": c["model"], "max_tokens": max_tokens, "temperature": 0, "system": system,
                          "messages": [{"role": "user", "content": user}]},
                         {"x-api-key": c["key"], "anthropic-version": "2023-06-01"})
            return data["content"][0]["text"]
        url = c["base"].rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {c['key']}"} if c["key"] else {}
        if c["provider"] == "azure":
            url += "?api-version=" + c["api_version"]
            headers = {"api-key": c["key"]}
        body = {"model": c["model"], "temperature": 0, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        data = _post(url, body, headers)
        return data["choices"][0]["message"]["content"]

    return _cached("chat", payload, call)


def chat_json(system, user, profile="slm", max_tokens=800):
    text = chat(system, user, profile, max_tokens, json_mode=True)
    m = re.search(r"\{.*\}|\[.*\]", text, re.S)
    if not m:
        raise SLMError(f"model did not return JSON: {text[:200]!r}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise SLMError(f"bad JSON from model: {e}")


def embed(texts):
    if not embed_enabled():
        raise SLMError("embedding model not configured")
    base, model = os.environ["SLM_BASE_URL"].rstrip("/"), os.environ["SLM_EMBED_MODEL"]
    headers = {"Authorization": f"Bearer {os.environ['SLM_API_KEY']}"} if os.environ.get("SLM_API_KEY") else {}
    out = []
    for i in range(0, len(texts), 64):
        batch = texts[i:i + 64]
        data = _cached("embed", {"m": model, "x": batch},
                       lambda b=batch: _post(base + "/embeddings", {"model": model, "input": b}, headers))
        out += [d["embedding"] for d in sorted(data["data"], key=lambda d: d["index"])]
    return out


def rerank(query, docs):
    """Scores for docs (same order). Uses the Jina/Cohere-style /rerank endpoint that vLLM and TEI expose."""
    if not rerank_enabled():
        raise SLMError("rerank model not configured")
    base, model = os.environ["SLM_BASE_URL"].rstrip("/"), os.environ["SLM_RERANK_MODEL"]
    headers = {"Authorization": f"Bearer {os.environ['SLM_API_KEY']}"} if os.environ.get("SLM_API_KEY") else {}
    data = _cached("rerank", {"m": model, "q": query, "d": docs},
                   lambda: _post(base + "/rerank", {"model": model, "query": query, "documents": docs}, headers))
    scores = [0.0] * len(docs)
    for r in data.get("results", []):
        scores[r["index"]] = float(r.get("relevance_score", r.get("score", 0.0)))
    return scores


def cosine(a, b):
    num = sum(x * y for x, y in zip(a, b))
    da = sum(x * x for x in a) ** 0.5
    db = sum(y * y for y in b) ** 0.5
    return num / (da * db) if da and db else 0.0
