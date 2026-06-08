# clinical-mcp-server

**MCP server exposing clinical-literature + drug-label search** to Claude Desktop and any other MCP client. Two tools, both backed by public US government APIs — no auth, no cost, no PHI.

`MCP` · `FastMCP` · `Claude Desktop` · `Anthropic` · `NCBI PubMed E-utils` · `openFDA` · `Pydantic v2` · `httpx` · `respx` · `pytest-asyncio`

| Tool | What it does | Backed by |
|---|---|---|
| `search_pubmed_tool` | PubMed query with field tags / MeSH / booleans → list of papers with PMID, authors, journal, DOI, year, and a clickable PubMed URL | [NCBI E-utils](https://www.ncbi.nlm.nih.gov/books/NBK25497/) |
| `get_drug_label_tool` | Brand / generic / substance name → curated FDA label sections (indications, dosing, contraindications, warnings, boxed warning, interactions) + DailyMed SPL link | [openFDA](https://open.fda.gov/apis/drug/label/) |

---

## Use it from Claude Desktop

1. **Install**

```bash
git clone https://github.com/odanree/clinical-mcp-server
cd clinical-mcp-server
python -m venv .venv && .venv/Scripts/activate
pip install -e ".[dev]"
```

2. **Drop these settings into your Claude Desktop config** (`%APPDATA%\Claude\claude_desktop_config.json` on Windows, `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "clinical": {
      "command": "C:\\Users\\Danh\\Documents\\Projects\\clinical-mcp-server\\.venv\\Scripts\\python.exe",
      "args": ["-m", "server.main"],
      "env": {
        "NCBI_API_KEY": "",
        "NCBI_EMAIL": "you@example.com"
      }
    }
  }
}
```

3. **Restart Claude Desktop.** The tool icon (🔧) in the input row should now list `search_pubmed_tool` and `get_drug_label_tool`. Try:

> "What does the recent literature say about metformin and cardiovascular outcomes in CKD patients?"
>
> "Pull the FDA label for atorvastatin — focus on the contraindications and boxed warning."

Claude will call the tools as needed and cite the returned URLs.

Full setup notes (rate-limit gotchas, API keys, troubleshooting) live in [docs/claude-desktop-config.md](docs/claude-desktop-config.md).

---

## Use it as a remote HTTP MCP server

For custom clients or web-hosted setups:

```bash
python -m server.main --transport http --host 0.0.0.0 --port 8765
# now serving the MCP streamable-HTTP transport at http://127.0.0.1:8765/mcp
```

A LangGraph agent in `agent/` (next session) will consume this transport directly.

---

## Why this exists

[MCP](https://modelcontextprotocol.io) is the emerging standard for letting an LLM call external tools without bespoke per-client glue. Most senior-AI portfolios still don't have an MCP project — this is the cheapest possible "I'm tracking the bleeding edge" signal you can ship.

**Why these two tools specifically**:
- PubMed is the canonical source of clinical primary literature. Every clinical question worth grounding hits it.
- openFDA labels are the only source of structured prescribing information that's machine-readable and free. Without them, an LLM has to summarize from training data — which is exactly the hallucination case.

**What's left for v2** (agent layer, in [`agent/`](agent/) when it lands):
- LangGraph supervisor that consumes this MCP server as its tool provider
- 20-case golden eval set (clinical questions with known answers + sources)
- Compliance workflow: "given guideline X, find all primary studies it cites, flag contradictions"

---

## Known limitations

### `get_drug_label` can silently return the wrong product

> Tracked: [#1 — get_drug_label silently returns wrong product on combo-drug ambiguity](https://github.com/odanree/clinical-mcp-server/issues/1)

The tool falls through `brand → generic → substance` and returns the first opening match. For ambiguous generic-name queries (e.g. `empagliflozin`) this can surface a **combination product** (Synjardy = empagliflozin + metformin) ahead of the monotherapy product (Jardiance = empagliflozin). The combo product's boxed warning belongs to the *other* active ingredient.

**Workaround until #1 ships:** query by **brand name** when you can. `get_drug_label("Jardiance")` returns the correct monotherapy label; `get_drug_label("empagliflozin")` does not.

This was caught the moment the server went live — the kind of failure the unit tests miss but evals against real public APIs catch. Fix is scoped for v0.2.

---

## Tests

```bash
pytest
# 10 tests covering both tools with mocked HTTP via respx — no network calls
```

Tests use [`respx`](https://github.com/lundberg/respx) to mock NCBI + openFDA so the suite stays fast and offline.

---

## Project layout

```
server/
  main.py            FastMCP entrypoint (stdio + http transports)
  config.py          pydantic-settings
  tools/
    pubmed.py        E-utils esearch + esummary
    openfda.py       /drug/label.json with brand→generic→substance fallback
tests/
  test_pubmed.py     respx-mocked PubMed queries
  test_openfda.py    respx-mocked openFDA queries
agent/               LangGraph agent that consumes this server (next session)
docs/
  claude-desktop-config.md   Setup notes + troubleshooting
```

---

## License

MIT
