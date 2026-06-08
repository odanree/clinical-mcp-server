"""Tests for the PubMed E-utils search tool — mocked HTTP, no network."""

from __future__ import annotations

import httpx
import pytest
import respx

from server.tools.pubmed import PubmedArticle, search_pubmed


@respx.mock
@pytest.mark.asyncio
async def test_search_pubmed_returns_normalized_articles():
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(
            200,
            json={"esearchresult": {"idlist": ["39000001", "39000002"]}},
        )
    )
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi").mock(
        return_value=httpx.Response(
            200,
            json={
                "result": {
                    "39000001": {
                        "title": "Metformin and cardiovascular outcomes in CKD.",
                        "fulljournalname": "New England Journal of Medicine",
                        "pubdate": "2024 Apr 14",
                        "authors": [{"name": "Smith J"}, {"name": "Patel R"}],
                        "articleids": [{"idtype": "doi", "value": "10.1056/test"}],
                    },
                    "39000002": {
                        "title": "Statin intolerance: pharmacogenomic considerations.",
                        "fulljournalname": "Lancet",
                        "pubdate": "2023",
                        "authors": [{"name": "Garcia M"}],
                        "articleids": [],
                    },
                }
            },
        )
    )

    async with httpx.AsyncClient() as client:
        results = await search_pubmed("metformin AND cardiovascular", client=client)

    assert len(results) == 2
    assert isinstance(results[0], PubmedArticle)
    assert results[0].pmid == "39000001"
    assert results[0].year == 2024
    assert results[0].doi == "10.1056/test"
    assert results[0].url == "https://pubmed.ncbi.nlm.nih.gov/39000001/"
    assert results[0].authors == ["Smith J", "Patel R"]
    assert results[1].year == 2023
    assert results[1].doi is None


@respx.mock
@pytest.mark.asyncio
async def test_search_pubmed_returns_empty_when_esearch_has_no_ids():
    respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": []}})
    )

    async with httpx.AsyncClient() as client:
        results = await search_pubmed("totallymadeupdrug123", client=client)
    assert results == []


@respx.mock
@pytest.mark.asyncio
async def test_search_pubmed_clamps_max_results():
    """1 <= max_results <= 50 — caller can't blow past PubMed's per-call cap."""
    esearch = respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
        return_value=httpx.Response(200, json={"esearchresult": {"idlist": []}})
    )

    async with httpx.AsyncClient() as client:
        await search_pubmed("q", max_results=99999, client=client)
        await search_pubmed("q", max_results=0, client=client)
        await search_pubmed("q", max_results=-5, client=client)

    # Inspect the actual outgoing retmax values.
    retmax_values = [
        call.request.url.params.get("retmax")
        for call in esearch.calls
    ]
    assert retmax_values == ["50", "1", "1"]


def test_from_esummary_handles_messy_pubdate():
    summary = {
        "uid": "12345678",
        "title": "Probe",
        "pubdate": "  2019 Jan-Feb ",
        "authors": [{"name": "Doe J"}],
    }
    a = PubmedArticle.from_esummary(summary)
    assert a.year == 2019


def test_from_esummary_handles_missing_year():
    a = PubmedArticle.from_esummary({"uid": "1", "title": "x", "pubdate": "not-a-date"})
    assert a.year is None
