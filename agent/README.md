# Agent layer (placeholder)

This subdirectory will hold a **LangGraph compliance agent** that consumes the parent MCP server as its tool provider — same `search_pubmed_tool` + `get_drug_label_tool` interface that Claude Desktop sees, just via the HTTP/SSE transport instead of stdio.

## Why a custom agent on top of an MCP server?

Claude Desktop is the perfect demo for "this MCP server is real." But for a compliance / regulatory-affairs use case, you typically want:

- A **deterministic workflow**: "given a clinical guideline, retrieve every primary study it cites, then check whether each one's conclusions still hold given more recent PubMed indexing."
- A **scored eval loop**: 20-case golden set, faithfulness + citation precision + refusal correctness, judged via [evalkit](https://github.com/odanree/evalkit).
- A **bring-your-own-frontend** path — Next.js, Slack, an internal portal — that can't talk MCP-stdio.

That's the LangGraph agent. It'll sit here in v2.

## Planned architecture

```
┌────────────────────┐         ┌────────────────────┐
│   Custom Next.js   │         │   Claude Desktop   │
│   compliance UI    │         │   (still works,    │
│                    │         │   stdio transport) │
└─────────┬──────────┘         └──────────┬─────────┘
          │                                │
          │ HTTP / SSE                     │ stdio
          ▼                                ▼
┌─────────────────────────────────────────────────────┐
│                LangGraph compliance agent           │
│  router → retrieval → critique → summarize          │
│                                                     │
│   tools wrapped over MCP client to the parent       │
│   server (no code duplication)                      │
└─────────────────────────────────┬───────────────────┘
                                  │
                  ┌───────────────▼────────────┐
                  │   clinical-mcp-server      │
                  │   (parent dir, HTTP mode)  │
                  └────────────────────────────┘
```

## Status

Not started. Will land in a follow-up session.
