# Design Brief: Sapiduct

> Owner: Sunkanmi Olawuwo · Date: 2026-10-28 · Status: Draft for owner review (Phase 2 of the design flow)
> Sources: the product conversation of 2026-10-28 (scope, roadmap, naming, auth and look decisions), `supporting-documents/research/inspiration-teardown.md`, and the generated frontend in `frontend/`. The grill phase was folded into that conversation; the decisions it settled are listed under "Decisions already made".

## Problem

Someone has material they know well: a folder of PDFs, course transcripts, a Notion workspace, a product's docs. They want their AI assistant (Claude Desktop, Cursor, ChatGPT) to answer from that material and show where each answer came from. Today that means either pasting files into every chat, or building and hosting an MCP server themselves: parsing, chunking, embedding, search, auth, a public endpoint. Public docs have products for this (Mintlify and GitBook ship an MCP server with every docs site; Context7 serves popular libraries). Private, mixed-format material has none that I found, and anyone who tries a DIY route cannot tell whether the assistant picks the right tool or cites the right passage.

A second user has the same problem with learning material: a course's videos, notes and assignments sit in separate places, and a learner cannot ask one question across all of them with citations.

## Solution

Sapiduct turns a set of your documents into one hosted MCP server you can connect to in a minute. You create a **collection**, add documents (upload, then later crawl a site or connect Notion), and Sapiduct indexes them and gives the collection **one MCP server** with a URL and an access token. A copy-paste snippet connects it to Claude Desktop or Cursor. Before you connect anything, a **playground** lets you try the tools by hand and see exactly what comes back, with the cited passages.

A collection can be switched into **course mode** (CourseLens): the same documents also become a syllabus, session digests, quizzes with spaced repetition and Socratic hints. Course mode is a module on top of the platform, not a separate product.

## Decisions already made

| Decision | Choice | Source |
|---|---|---|
| Model | A user has many collections; each collection has exactly one MCP server | Owner, 2026-10-28 |
| Backend and frontend | FastAPI with pgvector, Next.js, from the house templates | Owner |
| MCP library | FastMCP mounted inside the FastAPI app, token auth per collection, stateless HTTP | Recommendation accepted in the conversation; to be confirmed in an architecture record |
| User login | Supabase Auth behind one swappable `authenticate()` function | Recommendation accepted ("go"); to be verified against Supabase's current limits before build |
| Sign-in methods | GitHub and Google only; no email-and-password | Owner, 2026-10-28 |
| Look | Hybrid: calm warm shell for collections and documents, dense warm-dark panels for the MCP, playground and activity areas | Recommendation accepted |
| Theme | Light and dark, following the system; designed light first | Recommendation accepted |
| Playground | Link to MCPJam plus an in-app tool list and manual-call form; a chat panel comes last | Owner asked for B and C panels |
| Name and host | Sapiduct, at `sapiduct.olaheavy.dev` | Owner |

## Audiences and jobs to be done

1. **The builder (primary):** a developer or technical writer with private material who wants an assistant to use it. *Job:* "Make my documents available to my AI tools, and prove it works, in under ten minutes."
2. **The learner (course mode):** someone studying from a course's materials. *Job:* "Ask a question across everything I was given, get a cited answer, and be tested on it."
3. **The evaluator (portfolio visitor):** a hiring manager or founder who opens the live demo or the repo. *Job:* "See in a minute that this person ships real full-stack AI work." This audience shapes the landing page and the public demo content, not the product's day-to-day screens.

## What success looks like

- A new user goes from sign-up to a working connection in Claude Desktop in under ten minutes, without reading documentation. This is a target to measure with a timed walkthrough once built, not a claim.
- Every answer in the playground shows which passages it used.
- The collection page tells the owner at a glance whether the server is healthy, how fresh the index is, and whether anything is calling it.

## Experience Principles

1. **Show the proof.** Every answer, tool result and number points to its source: the passage, the document, the call. This resolves the tension between a smooth experience and a trustworthy one, in favour of trust.
2. **One connection, no ceremony.** The path from "I have documents" to "my assistant uses them" is the product. When a screen must choose between a feature and shortening that path, the path wins. This resolves the tension between breadth and speed.
3. **Calm to read, exact to work.** Reading screens (documents, course material) are spacious and quiet; working screens (server, playground, activity) are dense, monospaced where it helps, and show raw detail on demand. This resolves the tension between a learner's comfort and a developer's need for precision.

## Aesthetic Direction

- **Philosophy:** *Flow editorial*: warm paper and ink for the shell, warm near-black for technical panels, a single flow motif (lines or water moving through a duct) as the identity device, and one accent colour used sparingly. It is the house editorial approach of the personal website, shifted from travel to plumbing: where the website has a dotted route and tickets, Sapiduct has a flow line and tool cards.
- **Tone:** calm, exact, quietly confident. Playful only in small, bounded places (empty states, the ingestion progress animation).
- **Palette (direction, exact values in the tokens phase):** warm off-white and ink for the shell; stone-warm dark for technical panels; one accent that works on both (the teardown's three MCP-registry references converge on orange or emerald on a warm dark, so the choice is between those; decided in tokens with contrast checked); status colours kept separate from the accent.
- **Type (direction):** a distinctive display face with a warm character for headings and the landing page; a quiet sans for body at 16px or larger; a monospace for URLs, tokens, tool names and logs. Chosen and loaded in the tokens phase, not in this brief.
- **Motion:** short and purposeful, with the website's easing family (expo-out reveals, a small spring for confirmations). The flow motif animates only during real activity (an ingestion in progress, a call arriving) and is static otherwise. Everything non-essential is off under `prefers-reduced-motion`.
- **Reference points** (from `supporting-documents/research/inspiration-teardown.md`):
  - *Context7:* the copyable install command above the fold; the dense directory table.
  - *MCPJam:* a real product screenshot as the hero; side-by-side model comparison; suggested prompts under the chat.
  - *Smithery:* one concentrated personality device on a technical product; metadata on cards.
  - *Mintlify:* a generative line motif behind a dark product hero.
  - *Notion:* a calm shell with an inline highlighted word in the headline.
  - *Vercel and Supabase sign-in:* short auth pages with one primary action; Supabase's split layout with a brand panel.
  - *Udemy (CourseLens only):* the expandable course outline with lesson metadata and the "what you'll learn" checklist.
- **Anti-references:** generic dark "developer terminal" pages; AI gradient blobs; intro loaders; testimonial walls and customer logos while there are no customers; marketplace chrome (prices, carts, reviews); dense grey-on-black tables without hierarchy; a mascot that talks without substance.

## Existing Patterns

The frontend was generated from `house-template-nextjs` v0.3.0 and the backend from `house-template-fastapi` v0.6.1. The design extends them.

- **Framework:** Next.js 16 App Router with React 19, strict TypeScript, Tailwind 4.3, `src/` layout. No component library is installed: no Radix, shadcn or icon package. Adding one needs the owner's approval (AGENTS.md, "Ask before adding a dependency").
- **Tokens:** `frontend/src/styles/tokens.css` is a neutral starter set with semantic names: `bg-primary/secondary/tertiary/inverse`, `text-primary/secondary/tertiary/inverse/link`, `border-primary/secondary`, `focus-ring`, `accent-primary` and `-hover`, `status-success/warning/danger`, three radii, and system font stacks. Dark mode follows the system, with `data-theme` overriding. The template's tests check that every text colour passes WCAG AA on every background and that interactive borders and focus rings pass 3:1. The brief keeps these names and changes the values, which is the template's documented way to re-skin.
- **Missing from the starter set that the tokens phase must add:** spacing scale, a type ramp, shadows, motion durations and easings, a monospace surface palette for the technical panels, and component-level tokens.
- **Checks:** Playwright with axe (WCAG 2.2 AA) and screenshot comparison in light, dark and phone width, plus a CSP per request. New pages need their e2e entries and screenshots.
- **Pages today:** a placeholder home, `/health`, error pages, and a same-origin `/api/*` proxy with a typed client. Nothing else exists to preserve.
- **Backend contract:** the UI talks to the FastAPI `/v1` API through the typed client generated from its OpenAPI schema (`make api-types`). The brief's screens assume endpoints that do not exist yet; the architecture records define them.

## Component Inventory

| Component | Status | Notes |
|---|---|---|
| Design tokens (extended) | Modify | Same names, new values, plus the missing categories above |
| App shell (top bar, collection switcher, user menu) | New | Calm shell; the technical areas switch to the dark surface palette |
| Sign-in page | New | One page: Continue with GitHub or Google, a cancelled or failed state, and a brand panel; no password pages (owner decision, 2026-10-28) |
| Document list for large collections | New | Search, status chips with server counts, sort, cursor pager, batch progress strip, Retry all failed |
| Collection card | New | Name, mode badge (Knowledge or Course), document count, last indexed, calls this week, health dot |
| Create-collection flow | New | Name, optional mode, first documents; ends on the Documents tab |
| Collection tab bar (Documents, MCP server, Playground, Activity, Settings) | New | Course mode adds a Course tab |
| Document list and upload zone | New | Table with type, size, status (queued, parsing, indexed, failed with reason), re-index and remove actions; drag-and-drop with a file-type and size limit shown up front |
| Ingestion progress | New | Per-document state, using the flow motif; announced politely to screen readers |
| Connect panel (URL, token, config snippets) | New | Copy buttons; Claude Desktop and Cursor tabs; token shown once on creation, then masked; rotate and revoke |
| Tool list (playground panel 1) | New | Names, descriptions and input schemas read from the server's `tools/list` |
| Manual call form (playground panel 2) | New | Form generated from each tool's JSON schema; raw request, raw result, cited passages side by side |
| "Test in MCPJam" link | New | Link plus a copy-paste box; a prefilled link is unconfirmed (see Open decisions) |
| Chat with trace (playground panel 3) | New, last | Model picks tools; each call, its arguments and its result shown inline; rate-limited or bring-your-own-key |
| Citation chip and passage viewer | New | Used in the playground, in course mode answers, and in any answer view; deep-links to the document and passage |
| Activity log | New | Recent calls: time, tool, arguments, latency, result size, status; filter by status |
| Empty, loading and error states | New | One written pattern per screen; the flow motif appears in empty states only |
| Landing page (hero with real product shot, connect snippet, how it works, CourseLens section) | New | The evaluator's entry point; no customer logos or testimonials |
| Course mode: syllabus outline, concept map, session digest, quiz, hint panel | New | CourseLens module; the Udemy outline pattern without commerce |
| Theme toggle | New | Follows the system by default; persisted; no flash |
| Toast | New | Confirmations and errors, polite live region |

## Key Interactions

- **First run:** sign up, land on an empty Collections page with one primary action ("Create your first collection") and a link to a sample collection built from an openly licensed document set. No tour, no modal.
- **Add documents:** drop files on the zone; each row appears immediately as queued and moves through parsing and indexing. A failed document shows its reason and a retry. The collection is usable as soon as one document is indexed.
- **Connect:** the MCP server tab opens with the URL and the token (shown once). Choosing "Claude Desktop" or "Cursor" swaps the snippet. Copy confirms with a toast and a changed label, not a modal.
- **Try before you connect:** the playground lists the tools. Selecting one shows its description and a form; running it shows the request, the response and the cited passages. Nothing is hidden: "Show raw" is one click.
- **Token management:** rotate creates a new token and keeps the old one valid for a short, stated overlap; revoke is immediate and asks for confirmation naming the collection.
- **Activity:** new calls appear without a reload. The motif pulses once per call, only while the tab is open and motion is allowed.
- **Course mode:** switching a collection to course mode adds the Course tab; the syllabus and digests are generated from the indexed documents and every claim cites a passage. Assignment help gives hints, never full solutions (from the CourseLens definition).
- **Auth:** GitHub or Google only, on one page for new and returning users. A cancelled or failed sign-in returns to the page with a plain message and the other provider offered. A successful sign-in returns to the page the user came from.
- **Large collections:** the document list shows 25 at a time with search, status filters and a cursor pager. A batch upload is one progress strip, and the list does not reorder while documents finish. The MCP `list_sources` tool is paginated the same way.
- **Theme:** toggle in the user menu; follows the system by default; persisted; no flash on load.

## Responsive Behavior

- **≥1280px:** a left rail lists collections; the collection page shows its tab bar and a wide working area; the playground uses two columns (tool list and form on the left, request and result on the right).
- **768–1279px:** the rail collapses to a top switcher; the playground columns stack with the result under the form.
- **<768px:** the app is usable but not designed for heavy work. Collections, documents, connect and activity are fully supported; the playground works single-column with the raw request and result behind disclosures. Auth and landing pages are fully responsive. Touch targets are at least 44px; nothing depends on hover.

## Accessibility Requirements

- WCAG 2.2 AA, including mid-animation states; text contrast at least 4.5:1 and interactive edges and focus rings at least 3:1, in both themes (the template's token tests keep enforcing this for the new values).
- Every flow is keyboard-operable: upload (with a real button, not only drop), the tab bar, the tool list, the manual-call form, copy buttons, and token rotate and revoke dialogs, with focus trapped in dialogs and returned on close.
- A visible focus ring in both themes; a skip-to-content link.
- Status is never colour alone: the health dot has a text label; ingestion states are words plus an icon.
- Streaming and progress output use polite live regions in sentence-sized chunks; the flow motif and any decorative SVG are `aria-hidden`.
- `prefers-reduced-motion` turns off the motif animation, spring confirmations and any auto-pulsing.
- Form errors are associated with their fields; forms do not time out.

## Claims policy

- No customer logos, testimonials, user counts or revenue figures until they exist and are sourced.
- Every number shown in the product comes from the API and the data, and every figure in marketing copy carries its source or is labelled as a measurement of the demo, with its dataset.
- Comparisons with other products are limited to what their own pages say, with a link; the Smithery shutdown notice is quoted only if re-checked and linked at the time of publishing.
- Demo content is the owner's own or openly licensed with attribution (the research note lists candidates). Course materials from the FDE bootcamp never appear publicly (the owner's rule that course materials stay private; no decision record exists in this repo yet).
- "Works with Claude Desktop and Cursor" is stated only after each connection has been tested end to end and the date recorded.

## Out of Scope

- Billing, plans and payments; team workspaces and sharing; an admin back office.
- A marketplace or public directory of collections.
- Connectors beyond file upload in the first build (URL crawl, Notion, Drive and GitHub come after, each with its own brief section).
- The model-in-the-loop chat panel in the first build (specified here, built last).
- A native mobile app.
- OAuth for MCP clients; access is by token.
- Real-time collaboration, comments, and document editing inside Sapiduct.

## Open decisions

1. **Accent colour:** orange or emerald (tokens phase, decided by contrast and by how it sits on the warm dark).
2. **Display font:** a warm serif or a soft grotesk; must be checked for licence and loading cost (tokens phase).
3. **MCPJam prefill:** whether the hosted app accepts a prefilled server URL; unconfirmed. The link falls back to copy-paste if not.
4. **Supabase Auth limits and any OAuth-provider support:** verify before the auth build. The login function stays swappable.
5. **Hosting risk:** Smithery's shutdown notice for its proxy and identity services (dialog read on 2026-10-28, no year shown, explanation not yet read). Read it before committing to running public endpoints for other people's data, and decide the free-tier limits and abuse controls in the architecture records.
6. **Repository visibility:** `AGENTS.md` says public; the repository is currently private. The owner said public is fine; the change has not been made yet.
