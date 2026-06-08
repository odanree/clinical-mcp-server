"""
PubMed E-utils search tool.

API surface:
  https://www.ncbi.nlm.nih.gov/books/NBK25497/

Two-step protocol:
  esearch.fcgi  → returns matching PMIDs for a query
  esummary.fcgi → returns title/authors/journal/abstract for those PMIDs

NCBI rate limits:
  3 req/sec without an API key
  10 req/sec with an API key
We respect both via a small sleep between calls.

All responses are normalized to a stable internal shape, so downstream
LLMs and the test suite see deterministic structure regardless of NCBI
field ordering.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field

from server.config import settings

log = logging.getLogger(__name__)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_DB = "pubmed"
DEFAULT_RETMAX = 10
TIMEOUT_S = 15.0


class PubmedArticle(BaseModel):
    """One PubMed result as the MCP client sees it."""

    pmid: str
    title: str
    authors: list[str] = Field(default_factory=list)
    journal: str = ""
    year: int | None = None
    abstract: str = ""
    doi: str | None = None
    url: str

    @classmethod
    def from_esummary(cls, summary: dict[str, Any]) -> PubmedArticle:
        """Normalize NCBI's esummary JSON shape into our model."""
        pmid = str(summary.get("uid") or summary.get("pmid") or "")
        title = (summary.get("title") or "").strip()
        journal = (summary.get("fulljournalname") or summary.get("source") or "").strip()
        # NCBI dates look like "2024 Mar 14" or "2024".
        pubdate = summary.get("pubdate") or ""
        year: int | None = None
        for token in pubdate.split():
            if token.isdigit() and len(token) == 4:
                year = int(token)
                break
        authors = [
            (a.get("name") or "").strip()
            for a in summary.get("authors", [])
            if (a.get("name") or "").strip()
        ]
        doi = None
        for ai in summary.get("articleids", []):
            if (ai.get("idtype") or "").lower() == "doi":
                doi = ai.get("value")
                break
        return cls(
            pmid=pmid,
            title=title,
            authors=authors,
            journal=journal,
            year=year,
            abstract="",  # filled in by efetch in a later iteration
            doi=doi,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        )


def _common_params() -> dict[str, str]:
    """Identifying params NCBI asks every E-utils caller to send."""
    params: dict[str, str] = {"tool": settings.ncbi_tool_name}
    if settings.ncbi_email:
        params["email"] = settings.ncbi_email
    if settings.ncbi_api_key:
        params["api_key"] = settings.ncbi_api_key
    return params


async def search_pubmed(
    query: str,
    max_results: int = DEFAULT_RETMAX,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[PubmedArticle]:
    """Search PubMed and return summarized results.

    Args:
        query: PubMed query string. Supports MeSH terms, field tags
            (`metformin[Title]`, `cardiology[Mesh]`), boolean operators, etc.
        max_results: Hard cap on returned articles (PubMed default is 20,
            we default to 10 to keep MCP tool latency under 2 sec).
        client: Optional httpx.AsyncClient (used by tests to inject a mock).
    """
    max_results = max(1, min(max_results, 50))
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        pmids = await _esearch(client, query, max_results)
        if not pmids:
            return []
        await _polite_sleep()
        return await _esummary(client, pmids)
    finally:
        if own_client:
            await client.aclose()


async def _esearch(client: httpx.AsyncClient, query: str, retmax: int) -> list[str]:
    params = {
        **_common_params(),
        "db": DEFAULT_DB,
        "term": query,
        "retmode": "json",
        "retmax": str(retmax),
        "sort": "relevance",
    }
    r = await client.get(f"{BASE_URL}/esearch.fcgi", params=params)
    r.raise_for_status()
    data = r.json()
    return data.get("esearchresult", {}).get("idlist", [])


async def _esummary(client: httpx.AsyncClient, pmids: list[str]) -> list[PubmedArticle]:
    params = {
        **_common_params(),
        "db": DEFAULT_DB,
        "id": ",".join(pmids),
        "retmode": "json",
    }
    r = await client.get(f"{BASE_URL}/esummary.fcgi", params=params)
    r.raise_for_status()
    result = r.json().get("result", {})

    articles: list[PubmedArticle] = []
    for pmid in pmids:
        summary = result.get(pmid)
        if not summary:
            continue
        articles.append(PubmedArticle.from_esummary({**summary, "uid": pmid}))
    return articles


_LAST_CALL_TS = 0.0
_MIN_INTERVAL = 0.34  # ~3 req/sec without an API key (NCBI's stated limit)


async def _polite_sleep() -> None:
    """Cheap throttle that keeps us below NCBI's rate cap when bursting."""
    import time
    global _LAST_CALL_TS
    interval = 0.11 if settings.ncbi_api_key else _MIN_INTERVAL
    delta = time.monotonic() - _LAST_CALL_TS
    if delta < interval:
        await asyncio.sleep(interval - delta)
    _LAST_CALL_TS = time.monotonic()
