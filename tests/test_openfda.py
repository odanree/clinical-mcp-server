"""Tests for the openFDA drug-label tool — mocked HTTP, no network."""

from __future__ import annotations

import httpx
import pytest
import respx

from server.tools.openfda import DrugLabel, get_drug_label


def _label_record(brand: str, generic: str) -> dict:
    """Build the openFDA label envelope shape with sensible defaults."""
    return {
        "results": [
            {
                "set_id": "0000-1111-2222-3333",
                "indications_and_usage": [f"For treatment of high cholesterol ({generic})."],
                "dosage_and_administration": ["10-80 mg orally once daily."],
                "contraindications": ["Active liver disease."],
                "warnings": ["Risk of myopathy and rhabdomyolysis."],
                "adverse_reactions": ["Headache, myalgia, GI upset."],
                "drug_interactions": ["CYP3A4 inhibitors increase exposure."],
                "openfda": {
                    "brand_name": [brand],
                    "generic_name": [generic],
                    "manufacturer_name": ["Test Pharma Inc."],
                },
            }
        ]
    }


@respx.mock
@pytest.mark.asyncio
async def test_get_drug_label_returns_curated_label():
    respx.get("https://api.fda.gov/drug/label.json").mock(
        return_value=httpx.Response(200, json=_label_record("Lipitor", "atorvastatin"))
    )

    async with httpx.AsyncClient() as client:
        label = await get_drug_label("Lipitor", client=client)

    assert isinstance(label, DrugLabel)
    assert label.brand_name == "Lipitor"
    assert label.generic_name == "atorvastatin"
    assert label.manufacturer == "Test Pharma Inc."
    assert "high cholesterol" in (label.indications_and_usage or "")
    assert label.spl_url == (
        "https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid=0000-1111-2222-3333"
    )


@respx.mock
@pytest.mark.asyncio
async def test_get_drug_label_falls_through_brand_to_generic():
    """Brand-name search returns nothing → tool retries with generic_name."""
    route = respx.get("https://api.fda.gov/drug/label.json")
    route.side_effect = [
        httpx.Response(404),
        httpx.Response(200, json=_label_record("Lipitor", "atorvastatin")),
    ]

    async with httpx.AsyncClient() as client:
        label = await get_drug_label("atorvastatin", client=client)

    assert label is not None
    # Confirm both calls actually happened.
    assert len(route.calls) == 2
    assert "brand_name" in route.calls[0].request.url.params["search"]
    assert "generic_name" in route.calls[1].request.url.params["search"]


@respx.mock
@pytest.mark.asyncio
async def test_get_drug_label_returns_none_when_no_match_across_fields():
    respx.get("https://api.fda.gov/drug/label.json").mock(return_value=httpx.Response(404))

    async with httpx.AsyncClient() as client:
        label = await get_drug_label("totallymadeupdrug", client=client)
    assert label is None


@respx.mock
@pytest.mark.asyncio
async def test_get_drug_label_handles_empty_results_array():
    respx.get("https://api.fda.gov/drug/label.json").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    async with httpx.AsyncClient() as client:
        label = await get_drug_label("nothing", client=client)
    assert label is None


@respx.mock
@pytest.mark.asyncio
async def test_get_drug_label_handles_400_by_falling_through():
    """openFDA returns 400 on malformed queries — should fall to the next field."""
    route = respx.get("https://api.fda.gov/drug/label.json")
    route.side_effect = [
        httpx.Response(400, json={"error": "malformed query"}),
        httpx.Response(200, json=_label_record("Tylenol", "acetaminophen")),
    ]
    async with httpx.AsyncClient() as client:
        label = await get_drug_label("Tylenol", client=client)
    assert label is not None
    assert label.brand_name == "Tylenol"
