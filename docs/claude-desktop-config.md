# Claude Desktop setup

## Where the config lives

| OS | Path |
|---|---|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

If the file doesn't exist, create it with `{ "mcpServers": {} }` as the root.

## Minimal config

```json
{
  "mcpServers": {
    "clinical": {
      "command": "/abs/path/to/clinical-mcp-server/.venv/bin/python",
      "args": ["-m", "server.main"]
    }
  }
}
```

The `command` must be the absolute path to the Python interpreter **inside the project venv** — Claude Desktop doesn't activate venvs on your behalf. On Windows use `\\Scripts\\python.exe`; on macOS/Linux use `/bin/python`.

## Recommended config with API keys

NCBI bumps your PubMed rate limit from 3 to 10 requests per second when you set `NCBI_API_KEY` + `NCBI_EMAIL`. Get a free key at [account.ncbi.nlm.nih.gov](https://account.ncbi.nlm.nih.gov) → Settings → API Key Management.

openFDA defaults to a 240-request-per-minute limit which is fine for interactive use. If you hit it, request a free key at [open.fda.gov/apis/authentication/](https://open.fda.gov/apis/authentication/).

```json
{
  "mcpServers": {
    "clinical": {
      "command": "C:\\path\\to\\clinical-mcp-server\\.venv\\Scripts\\python.exe",
      "args": ["-m", "server.main"],
      "env": {
        "NCBI_API_KEY": "your-ncbi-key",
        "NCBI_EMAIL": "you@example.com",
        "OPENFDA_API_KEY": "your-openfda-key",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

## Verifying it works

1. Save the config and **fully quit Claude Desktop** (right-click the tray / dock icon → Quit). Reload via the menu doesn't reread `mcpServers`.
2. Reopen Claude Desktop and start a new chat.
3. Click the **🔧 tool icon** in the input row — it should expand to show the `clinical` server with two tools listed.

Try this prompt:

> "Use the clinical tools — find the three most-cited recent PubMed papers on SGLT2 inhibitors and heart failure, then pull the FDA boxed warning for empagliflozin if there is one."

Claude will call `search_pubmed_tool` then `get_drug_label_tool` and cite the URLs they return.

## Troubleshooting

**The 🔧 icon doesn't show the server**

Check Claude Desktop's MCP log:
- Windows: `%APPDATA%\Claude\logs\mcp-server-clinical.log`
- macOS: `~/Library/Logs/Claude/mcp-server-clinical.log`

Common causes:
- Wrong absolute path to `python.exe` / `python`
- venv isn't installed at the path you gave
- Working directory issue — try adding `"cwd": "C:\\path\\to\\clinical-mcp-server"` next to `command`

**Tools list but every call errors**

Run the server manually to verify it boots cleanly:

```bash
cd clinical-mcp-server
.venv/Scripts/python -m server.main
```

It should print nothing and wait for stdin (that's normal — stdio transport). Hit Ctrl-C. If it errored, fix that first.

**PubMed returns 429 / rate-limited**

You're hitting NCBI without an API key. Either add `NCBI_API_KEY` (gets you 10/sec) or accept that the tool will be throttled to 3/sec. The internal `_polite_sleep` already paces calls — this only happens when multiple clients share the same key.

**openFDA returns nothing for a drug I know exists**

The tool tries `openfda.brand_name` → `openfda.generic_name` → `openfda.substance_name`. If all three miss, the drug genuinely isn't in the openFDA label corpus (some older or veterinary drugs are absent). Falling back to a manual search at [open.fda.gov](https://open.fda.gov/) confirms.

## Removing the server

Delete the `"clinical"` entry from `mcpServers` and fully restart Claude Desktop.
