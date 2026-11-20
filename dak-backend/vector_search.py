import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase_client import get_supabase_admin

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
_gemini_client = None

def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set.")
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client

def embed_text(text: str) -> list[float]:
    """Generates a 768-dimensional embedding vector for input text."""
    client = get_gemini_client()
    try:
        res = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        if hasattr(res, "embeddings") and res.embeddings:
            return list(res.embeddings[0].values)
        if hasattr(res, "embedding") and res.embedding:
            return list(res.embedding.values)
        return []
    except Exception as e:
        print(f"[-] Error generating embedding: {e}")
        return []

_cached_local_docs = None

def _load_local_docs():
    global _cached_local_docs
    if _cached_local_docs is None:
        _cached_local_docs = []
        try:
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
            docs_dir = os.path.join(data_dir, "docs")
            if os.path.exists(docs_dir):
                for fname in os.listdir(docs_dir):
                    if fname.endswith(".txt"):
                        fpath = os.path.join(docs_dir, fname)
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            _cached_local_docs.append((fname, f.read()))
        except Exception:
            _cached_local_docs = []
    return _cached_local_docs

def search_documents(query: str, top_k: int = 3, match_threshold: float = 0.3) -> list[dict]:
    """Performs vector search or instant local knowledge retrieval."""
    results = []

    # 1. Quick local document search (0ms latency, cached in memory)
    try:
        local_docs = _load_local_docs()
        query_words = set(query.lower().split())

        matched_snippets = []
        for fname, content in local_docs:
            score = sum(1 for w in query_words if len(w) > 2 and w in content.lower())
            if score > 0:
                matched_snippets.append((score, fname, content[:1200]))

        matched_snippets.sort(key=lambda x: x[0], reverse=True)
        for score, fname, text in matched_snippets[:top_k]:
            results.append({
                "id": fname,
                "text": text,
                "similarity": 0.8,
                "source": fname,
                "source_display": fname.replace(".txt", "").replace("_", " ").title(),
                "metadata": {"source": fname}
            })
    except Exception as ex:
        pass

    if results:
        return results

    # 2. Supabase pgvector search fallback
    try:
        embedding = embed_text(query)
        if embedding:
            admin = get_supabase_admin()
            res = admin.rpc("match_documents", {
                "query_embedding": embedding,
                "match_threshold": match_threshold,
                "match_count": top_k
            }).execute()

            matches = res.data or []
            for m in matches:
                meta = m.get("metadata") or {}
                results.append({
                    "id": m.get("id"),
                    "text": m.get("content", ""),
                    "similarity": m.get("similarity", 0.0),
                    "source": meta.get("source", "Supabase Vector DB"),
                    "source_display": meta.get("scheme_name", meta.get("service", meta.get("source", "India Post Official Guide"))),
                    "metadata": meta
                })
    except Exception:
        pass

    return results

