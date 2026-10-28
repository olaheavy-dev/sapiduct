# 0003. Documentation sources for agents and decisions

Status: Proposed (the owner accepts by merging the pull request)

## Context

Agents (and people) decide things in this project from documentation: how FastMCP serves a tool, how Supabase recovers a password, which MCP specification revision to implement. `AGENTS.md` already says to check the docs for the pinned version, not memory, but gives agents no list of sources to check, and a decision record can't later show which version of the docs it relied on.

Two facts make the choice of source matter:

- The libraries move quickly and differ by version. FastMCP's own documentation says its unversioned pages describe FastMCP 4 and its `/v3/` pages describe FastMCP 3 ([FastMCP: AI-assisted development](https://gofastmcp.com/getting-started/ai-assisted-development.md), read 2026-10-28). The MCP documentation site lists the specification revisions 2026-07-28, 2025-11-25, 2025-06-18, 2025-03-26, 2024-11-05 and a draft, and does not say which is current ([modelcontextprotocol.io](https://modelcontextprotocol.io/llms.txt), read 2026-10-28).
- Documentation read through a tool is untrusted text. It can contain instructions aimed at the agent (prompt injection), and a hosted documentation server cannot be pinned to a version the way a local package can (the repo pins `next-devtools-mcp@0.4.0` in `.mcp.json`).

## Decision

1. **Sources agents use, in this order:**
   1. The installed package's own code and docstrings for the pinned version: the ground truth for what actually runs.
   2. The maintainers' own documentation for that version, fetched as Markdown or through the maintainers' own docs server.
   3. A third-party documentation index only to find a pointer, never as the only source for a decision.
2. **One docs server is added now: FastMCP's own** (`https://gofastmcp.com/mcp`, which the FastMCP documentation lists as its docs search for agents). It is read-only search over the maintainers' documentation for the library the whole product depends on.
3. **Context7 is not added now.** It would add a hosted third-party index that cannot be pinned, covers libraries anyone can submit, and sees every query, to save effort that official Markdown and the installed source already cover. Revisit if work shows a concrete gap (a library whose official docs cannot be read as Markdown or searched), and then through a new record.
4. **Supabase's documentation server is decided at the auth issue (#9)**, restricted to its docs tool group only. The server's database tools are not connected.
5. **The MCP specification is read as Markdown from modelcontextprotocol.io** (append `.md` to a page), so no server is needed. The record that fixes the MCP revision to implement is part of issue #5.
6. **Every decision record states** the library versions and the specification revision it was written against, and the date each source was read, next to the link in its Sources section.
7. **`.mcp.json` is owner-only:** `.github/CODEOWNERS` covers it. A new tool server is a new thing the agents trust, so the owner approves each one by merging the PR that adds it (`AGENTS.md`, rule 3).

### How the risks are handled

| Risk | Mitigation |
| --- | --- |
| Text from a docs source contains instructions to the agent | The hooks and permission settings the template installs apply whatever the text says (no push to `main`, secret reads denied, risky shell commands blocked). The docs server is read-only and queries carry library and API names, never keys or customer data. Advice taken from docs is checked against the pinned version and goes through tests and review like any change. |
| A hosted server changes, is compromised or shuts down | Only the maintainers' own server is used. Decisions depend on recorded versions, URLs and read dates, not on a server staying the same. The Markdown pages are the fallback, so work continues if the server is down. |
| The server sees what the agent asks | Queries contain no secrets or customer data. The server is the library maintainers' own. |
| A new tool server widens what the agents trust | Owner-only through CODEOWNERS and the PR gate (decision 7). |

## Consequences

- One remote entry in `.mcp.json` that can't be pinned; its trade-off is accepted here and rechecked whenever the FastMCP dependency is upgraded.
- Records take a little longer to write because versions and read dates are required.
- The entry follows Claude Code's HTTP server format and hasn't been exercised in a session yet: confirm it connects the first time a session is started in this repository.
- Generic parts (owner-only `.mcp.json`, versions and dates in records) are candidates to carry back to `house-template-base`.

## Alternatives considered

- **Context7 now:** broader coverage of the other libraries (FastAPI, SQLAlchemy, LangChain), at the cost of an unpinnable third-party index with unvetted content. Not needed yet; see decision 3.
- **No docs servers, only web fetch:** simpler, but gives no search over the library the product depends on.
- **Copying documentation into the repository:** pins the text, but risks stale copies and licence problems.

## Sources

- FastMCP, AI-assisted development (docs MCP at `https://gofastmcp.com/mcp`; unversioned pages describe FastMCP 4, `/v3/` pages FastMCP 3; Markdown by appending `.md`; read 2026-10-28): https://gofastmcp.com/getting-started/ai-assisted-development.md
- Model Context Protocol documentation (specification revisions and `.md` pages; read 2026-10-28): https://modelcontextprotocol.io/llms.txt
- Supabase MCP server (docs tool group; read 2026-10-28, setup details to be re-read at issue #9): https://github.com/supabase/mcp
- Context7 setup for Claude Code (mirror of its docs; remote endpoint and optional key; read 2026-10-28): https://www.mintlify.com/upstash/context7/mcp/claude-code
