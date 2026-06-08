"""
openFDA drug label lookup.

Endpoint:
  https://api.fda.gov/drug/label.json
  Docs: https://open.fda.gov/apis/drug/label/

We support search by brand name (consumer-facing) OR generic/active
ingredient. Both fall through to the same `search=` query string —
brand match is tried first, generic as a fallback.

Returned fields are intentionally a tight subset of the very wide
openFDA label schema. Full labels run hundreds of KB; LLMs do better
when handed a curated set of sections.
"""

from __future__ import annotations

import logging

import httpx
from pydantic import BaseModel, Field

from server.config import settings

log = logging.getLogger(__name__)

BASE_URL = "https://api.fda.gov/drug/label.json"
TIMEOUT_S = 12.0


class DrugLabel(BaseModel):
    """One curated FDA label section bundle returned to the MCP client."""

    brand_name: str | None = None
    generic_name: str | None = None
    manufacturer: str | None = None
    indications_and_usage: str | None = None
    dosage_and_administration: str | None = None
    contraindications: str | None = None
    warnings: str | None = None
    adverse_reactions: str | None = None
    boxed_warning: str | None = None
    drug_interactions: str | None = None
    set_id: str | None = Field(default=None, description="DailyMed SetID for cross-linking")
    spl_url: str | None = Field(default=None, description="Public Structured Product Label URL")


async def get_drug_label(
    name: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> DrugLabel | None:
    """Look up an FDA drug label by brand or generic name.

    Args:
        name: User-friendly drug name. Case-insensitive.
        client: Optional httpx.AsyncClient (tests inject mocks here).

    Returns the first match, or None when openFDA has no record.
    """
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=TIMEOUT_S)
    try:
        # Try brand name first — that's what users typically know.
        for field_path in (
            "openfda.brand_name",
            "openfda.generic_name",
            "openfda.substance_name",
        ):
            label = await _try_search(client, field_path, name)
            if label is not None:
                return label
        return None
    finally:
        if own_client:
            await client.aclose()


async def _try_search(
    client: httpx.AsyncClient,
    field_path: str,
    name: str,
) -> DrugLabel | None:
    # openFDA query syntax: search=field:"value"
    # quoting handles multi-word names like "tylenol extra strength"
    safe = name.replace('"', '').strip()
    params = {"search": f'{field_path}:"{safe}"', "limit": "1"}
    if settings.openfda_api_key:
        params["api_key"] = settings.openfda_api_key
    r = await client.get(BASE_URL, params=params)
    if r.status_code == 404:
        return None
    if r.status_code == 400:
        # Bad query — try the next field.
        log.debug("openFDA 400 for %s=%s, falling through", field_path, safe)
        return None
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        return None
    return _normalize(results[0])


def _first(value: list[str] | str | None) -> str | None:
    """openFDA label fields are usually [str] one-element lists. Flatten."""
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _normalize(record: dict) -> DrugLabel:
    openfda = record.get("openfda", {})
    set_id = _first(record.get("set_id"))
    spl_url = (
        f"https://dailymed.nlm.nih.gov/dailymed/lookup.cfm?setid={set_id}"
        if set_id else None
    )
    return DrugLabel(
        brand_name=_first(openfda.get("brand_name")),
        generic_name=_first(openfda.get("generic_name")),
        manufacturer=_first(openfda.get("manufacturer_name")),
        indications_and_usage=_first(record.get("indications_and_usage")),
        dosage_and_administration=_first(record.get("dosage_and_administration")),
        contraindications=_first(record.get("contraindications")),
        warnings=_first(record.get("warnings")),
        adverse_reactions=_first(record.get("adverse_reactions")),
        boxed_warning=_first(record.get("boxed_warning")),
        drug_interactions=_first(record.get("drug_interactions")),
        set_id=set_id,
        spl_url=spl_url,
    )
