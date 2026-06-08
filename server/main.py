"""
FastMCP entrypoint.

stdio is the default transport (what Claude Desktop uses). Pass --transport=http
to expose an HTTP/SSE endpoint that custom MCP clients can connect to.

Each registered tool is automatically described to the client with its
docstring + type annotations — what the LLM uses to decide when to call it.
"""

from __future__ import annotations

import argparse
import logging

from fastmcp import FastMCP

from server.config import settings
from server.tools.openfda import DrugLabel, get_drug_label
from server.tools.pubmed import PubmedArticle, search_pubmed

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger(__name__)

mcp: FastMCP = FastMCP(
    "clinical-mcp-server",
    instructions=(
        "Public clinical-knowledge tools backed by NCBI PubMed and openFDA. "
        "Use search_pubmed to find primary literature; use get_drug_label to "
        "fetch curated FDA label sections (indications, warnings, boxed warning, "
        "interactions). Both surface URLs back to the canonical source so the "
        "calling agent can cite. No PHI is involved — all data is public."
    ),
)


@mcp.tool()
async def search_pubmed_tool(query: str, max_results: int = 10) -> list[PubmedArticle]:
    """Search PubMed for clinical literature.

    Use this to ground answers about clinical questions in primary sources.
    Supports the full PubMed query language: MeSH terms, field tags
    (e.g. "metformin[Title]"), boolean operators, date ranges.

    Args:
        query: PubMed query string.
        max_results: Maximum number of results to return (1-50, default 10).

    Returns a list of articles with PMID, title, authors, journal, year,
    DOI, and a direct PubMed URL for citation.
    """
    return await search_pubmed(query, max_results=max_results)


@mcp.tool()
async def get_drug_label_tool(name: str) -> DrugLabel | None:
    """Fetch curated sections of an FDA drug label.

    Use this to ground answers about drug indications, dosing, contraindications,
    warnings, and interactions. Looks up by brand name first, then generic name,
    then active substance.

    Args:
        name: Drug name — brand (e.g. "Lipitor") or generic (e.g. "atorvastatin").

    Returns the most relevant FDA-approved label, or None if the drug isn't found.
    Includes a DailyMed Structured Product Label URL for citation.
    """
    return await get_drug_label(name)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the clinical-mcp-server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="Transport. stdio = Claude Desktop default. http/sse = networked clients.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run()
    elif args.transport in ("http", "sse"):
        # FastMCP's HTTP transport speaks streamable-HTTP/SSE — the spec for
        # remote MCP clients. The route is /mcp by default.
        mcp.run(transport="http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
