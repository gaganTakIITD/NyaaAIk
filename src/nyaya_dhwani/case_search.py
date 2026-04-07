"""Live precedent case search pipeline.

3-layer search strategy:
  Layer 1: Indian Kanoon API (primary — best quality, structured legal data)
  Layer 2: Google Custom Search restricted to legal sites (backup)
  Layer 3: Chunk Set 2 / Delta Lake pre-loaded cases (offline fallback)

Steps:
  1. LLM refines user query → structured legal search queries
  2. Multi-source search across 3 layers
  3. Semantic re-ranking using MiniLM embeddings
  4. Case metadata extraction + citation formatting
"""

from __future__ import annotations

import json
import logging
import os
import re
from html import unescape
from typing import Any

import numpy as np
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

_IK_TIMEOUT = 15  # seconds
_GOOGLE_TIMEOUT = 10


def _ik_token() -> str:
    return os.environ.get("INDIAN_KANOON_API_TOKEN", "").strip()


def _google_api_key() -> str:
    return os.environ.get("GOOGLE_API_KEY", "").strip()


def _google_cse_cx() -> str:
    return os.environ.get("GOOGLE_CSE_CX", "").strip()


# ---------------------------------------------------------------------------
# Step 1: LLM Query Refinement
# ---------------------------------------------------------------------------

_REFINE_SYSTEM = """\
You are a legal search query optimizer for Indian law.
Given a user's legal question, extract a JSON object with:
1. "legal_domain": one of criminal/civil/constitutional/family/property/consumer/labour
2. "bns_sections": list of relevant Bharatiya Nyaya Sanhita 2023 section numbers (strings), or empty list
3. "ipc_equivalent": corresponding old IPC section numbers (strings), or empty list
4. "search_queries": exactly 3 optimized search strings for finding Indian court judgments. Use legal terminology, include section numbers when known.
5. "keywords": 3-5 key legal terms
6. "court_hint": suggested court level — "supremecourt", "highcourts", or "all"

Respond with ONLY valid JSON, no markdown, no explanation."""


def refine_query(user_query: str) -> dict[str, Any]:
    """Use LLM to convert a raw user query into structured legal search queries.

    Falls back to a simple extraction if LLM call fails.
    """
    try:
        from nyaya_dhwani.llm_client import chat_completions, extract_assistant_text

        messages = [
            {"role": "system", "content": _REFINE_SYSTEM},
            {"role": "user", "content": user_query},
        ]
        raw = chat_completions(messages, max_tokens=512, temperature=0.1)
        text = extract_assistant_text(raw)
        # Strip markdown code fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text.strip())
        parsed = json.loads(text)
        logger.info("Query refined: domain=%s, queries=%s",
                     parsed.get("legal_domain"), parsed.get("search_queries"))
        return parsed
    except Exception as e:
        logger.warning("LLM query refinement failed, using fallback: %s", e)
        # Fallback: use the raw query as-is
        return {
            "legal_domain": "unknown",
            "bns_sections": [],
            "ipc_equivalent": [],
            "search_queries": [user_query],
            "keywords": user_query.split()[:5],
            "court_hint": "all",
        }


# ---------------------------------------------------------------------------
# Step 2: Multi-Source Search
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    clean = re.sub(r"<[^>]+>", "", text)
    return unescape(clean).strip()


# --- Layer 1: Indian Kanoon API ---

_IK_DOCTYPE_MAP = {
    "SC": "supremecourt",
    "HC": "highcourts",
    "DC": "",  # No specific filter for district courts on IK
    "all": "",
}


def search_indian_kanoon(
    query: str,
    *,
    num_results: int = 10,
    doctype_filter: str = "",
    token: str | None = None,
) -> list[dict]:
    """Search Indian Kanoon API for relevant cases.

    Args:
        query: Search query string.
        num_results: Max results to return.
        doctype_filter: e.g. "supremecourt", "highcourts", "judgments".
        token: API token (defaults to env var).

    Returns:
        List of case dicts with keys: doc_id, title, headline, court, date,
        judge, num_citations, source.
    """
    tok = token or _ik_token()
    if not tok:
        logger.warning("INDIAN_KANOON_API_TOKEN not set, skipping IK search")
        return []

    form_input = query
    if doctype_filter:
        form_input = f"{query}+doctypes:{doctype_filter}"

    try:
        r = requests.post(
            "https://api.indiankanoon.org/search/",
            data={"formInput": form_input, "pagenum": 0},
            headers={
                "Authorization": f"Token {tok}",
                "Accept": "application/json",
            },
            timeout=_IK_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("Indian Kanoon search failed: %s", e)
        return []

    cases = []
    for doc in data.get("docs", [])[:num_results]:
        cases.append({
            "doc_id": str(doc.get("tid", "")),
            "title": doc.get("title", "Unknown Case"),
            "headline": _strip_html(doc.get("headline", "")),
            "court": doc.get("docsource", ""),
            "date": doc.get("publishdate", ""),
            "judge": doc.get("author", ""),
            "num_citations": doc.get("numcitedby", 0),
            "doc_size": doc.get("docsize", 0),
            "source": "indian_kanoon",
            "url": f"https://indiankanoon.org/doc/{doc.get('tid', '')}/",
        })
    logger.info("Indian Kanoon: %d results for %r", len(cases), query[:80])
    return cases


def fetch_ik_document(doc_id: str, token: str | None = None) -> str:
    """Fetch full text of a specific judgment from Indian Kanoon.

    Args:
        doc_id: The document/tid ID.
        token: API token (defaults to env var).

    Returns:
        Full text (HTML-stripped) of the judgment.
    """
    tok = token or _ik_token()
    if not tok:
        return ""
    try:
        r = requests.post(
            f"https://api.indiankanoon.org/doc/{doc_id}/",
            headers={
                "Authorization": f"Token {tok}",
                "Accept": "application/json",
            },
            timeout=_IK_TIMEOUT,
        )
        r.raise_for_status()
        doc_html = r.json().get("doc", "")
        return _strip_html(doc_html)
    except Exception as e:
        logger.warning("Failed to fetch IK doc %s: %s", doc_id, e)
        return ""


# --- Layer 2: Google Custom Search ---

def search_google_cse(
    query: str,
    *,
    num_results: int = 10,
    api_key: str | None = None,
    cx: str | None = None,
) -> list[dict]:
    """Backup search using Google Custom Search Engine.

    The CSE should be restricted to legal sites (e.g. indiankanoon.org).
    """
    key = api_key or _google_api_key()
    engine_cx = cx or _google_cse_cx()
    if not key or not engine_cx:
        logger.debug("Google CSE not configured, skipping")
        return []

    try:
        r = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": key,
                "cx": engine_cx,
                "q": query,
                "num": min(num_results, 10),  # API max is 10 per page
            },
            timeout=_GOOGLE_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("Google CSE search failed: %s", e)
        return []

    cases = []
    for item in data.get("items", []):
        link = item.get("link", "")
        # Try to extract Indian Kanoon doc ID from URL
        doc_id = ""
        if "/doc/" in link:
            doc_id = link.split("/doc/")[-1].rstrip("/")

        cases.append({
            "doc_id": doc_id,
            "title": item.get("title", ""),
            "headline": item.get("snippet", ""),
            "court": "",
            "date": "",
            "judge": "",
            "num_citations": 0,
            "doc_size": 0,
            "source": "google_cse",
            "url": link,
        })
    logger.info("Google CSE: %d results for %r", len(cases), query[:80])
    return cases


# ---------------------------------------------------------------------------
# Step 3: Semantic Re-ranking
# ---------------------------------------------------------------------------

def rerank_cases(
    user_query: str,
    cases: list[dict],
    top_k: int = 7,
) -> list[dict]:
    """Re-rank case results by semantic similarity to the user query.

    Uses the same MiniLM model as the main RAG embedder.
    """
    if not cases:
        return []
    if len(cases) <= top_k:
        return cases

    try:
        from nyaya_dhwani.embedder import SentenceEmbedder
        embedder = SentenceEmbedder()

        query_emb = embedder.encode([user_query])[0]
        texts = [
            f"{c.get('title', '')} {c.get('headline', '')}".strip()
            for c in cases
        ]
        case_embs = embedder.encode(texts)

        # Cosine similarity
        query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-9)
        case_norms = case_embs / (
            np.linalg.norm(case_embs, axis=1, keepdims=True) + 1e-9
        )
        scores = case_norms @ query_norm

        ranked_indices = np.argsort(scores)[::-1][:top_k]
        return [cases[int(i)] for i in ranked_indices]
    except Exception as e:
        logger.warning("Semantic re-ranking failed, returning first %d: %s", top_k, e)
        return cases[:top_k]


# ---------------------------------------------------------------------------
# Step 4: Full text fetch + citation formatting
# ---------------------------------------------------------------------------

def enrich_cases_with_text(
    cases: list[dict],
    *,
    max_chars_per_case: int = 3000,
    max_fetch: int = 5,
) -> list[dict]:
    """Fetch full text for top cases from Indian Kanoon (enrichment).

    Only fetches for cases sourced from Indian Kanoon API.
    """
    for i, case in enumerate(cases[:max_fetch]):
        if case.get("source") == "indian_kanoon" and case.get("doc_id"):
            full_text = fetch_ik_document(case["doc_id"])
            if full_text:
                case["full_text"] = full_text[:max_chars_per_case]
            else:
                case["full_text"] = case.get("headline", "")
        else:
            case["full_text"] = case.get("headline", case.get("text", ""))
    return cases


def format_case_citation(case: dict) -> str:
    """Format a single case for citation in LLM context."""
    parts = [case.get("title", "Unknown")]
    if case.get("court"):
        parts.append(f"Court: {case['court']}")
    if case.get("date"):
        parts.append(f"Date: {case['date']}")
    if case.get("judge"):
        parts.append(f"Judge: {case['judge']}")
    if case.get("url"):
        parts.append(f"Source: {case['url']}")
    header = " | ".join(parts)

    text = case.get("full_text", case.get("headline", ""))
    return f"[CASE] {header}\n{text}"


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def search_precedent_cases(
    user_query: str,
    *,
    court_filter: str = "all",
    top_k: int = 7,
    max_fetch_text: int = 5,
    skip_refinement: bool = False,
) -> tuple[list[dict], dict]:
    """Complete live precedent case search pipeline.

    Args:
        user_query: The user's legal question (in English).
        court_filter: "SC", "HC", "DC", or "all".
        top_k: Number of final cases to return.
        max_fetch_text: Max cases to fetch full text for.
        skip_refinement: If True, skip LLM query refinement (use raw query).

    Returns:
        Tuple of (list of enriched case dicts, refinement metadata dict).
    """
    # --- Step 1: LLM Query Refinement ---
    if skip_refinement:
        refined = {
            "legal_domain": "unknown",
            "search_queries": [user_query],
            "keywords": [],
            "court_hint": "all",
        }
    else:
        refined = refine_query(user_query)

    # Map court filter to IK doctype
    doctype = _IK_DOCTYPE_MAP.get(court_filter.upper(), "")
    # Override with LLM's court hint if user didn't specify
    if court_filter == "all" and refined.get("court_hint", "all") != "all":
        doctype = _IK_DOCTYPE_MAP.get(
            refined["court_hint"].upper(),
            refined.get("court_hint", ""),
        )

    search_queries = refined.get("search_queries", [user_query])

    # --- Step 2: Multi-Source Search ---
    all_cases: list[dict] = []

    # Layer 1: Indian Kanoon API
    for sq in search_queries:
        ik_results = search_indian_kanoon(sq, num_results=10, doctype_filter=doctype)
        all_cases.extend(ik_results)

    # Layer 2: Google CSE (if Layer 1 got fewer than 5 results)
    if len(all_cases) < 5:
        for sq in search_queries[:2]:  # Limit to 2 queries for backup
            gcs_results = search_google_cse(sq, num_results=10)
            all_cases.extend(gcs_results)

    # Layer 3: Chunk Set 2 (Delta Lake fallback) — handled externally by caller
    # We just return what we have; caller combines with Vector Search results.

    if not all_cases:
        logger.warning("No cases found from any source for: %s", user_query[:80])
        return [], refined

    # --- Deduplicate by doc_id or title ---
    seen: set[str] = set()
    unique_cases: list[dict] = []
    for c in all_cases:
        key = c.get("doc_id") or c.get("title", "")
        if not key or key in seen:
            continue
        seen.add(key)
        unique_cases.append(c)

    logger.info("Deduplicated: %d unique cases from %d total", len(unique_cases), len(all_cases))

    # --- Step 3: Semantic Re-ranking ---
    top_cases = rerank_cases(user_query, unique_cases, top_k=top_k)

    # --- Step 4: Fetch full text for top cases ---
    enriched = enrich_cases_with_text(top_cases, max_fetch=max_fetch_text)

    return enriched, refined


def build_cases_context(cases: list[dict]) -> str:
    """Format all cases into a single context string for the LLM prompt."""
    if not cases:
        return "(No precedent cases found)"
    blocks = [format_case_citation(c) for c in cases]
    return "\n\n".join(blocks)
