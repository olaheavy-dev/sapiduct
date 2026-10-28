# Information Architecture: Sapiduct

> Phase 3 of the design flow · 2026-10-28 · Builds on `.design/sapiduct/DESIGN_BRIEF.md`
> The frontend today has only a placeholder home, `/health`, error pages and the `/api/*` proxy (from `house-template-nextjs` v0.3.0). Everything below is new. Stack: Next.js App Router, a FastAPI `/v1` API, Supabase Auth behind one swappable `authenticate()` function.

## Site Map

Routes are Next.js App Router paths. "Auth" means a signed-in user is required; a signed-out visitor is sent to `/sign-in` and returned afterwards.

- Landing `/` (public)
  - Try the demo `/demo`: a read-only sample collection with the playground, built from openly licensed documents (public)
  - Connect guides `/docs/connect/claude-desktop` and `/docs/connect/cursor` (public): the same snippets the app shows, with the date each was last tested
  - Privacy `/privacy` and Terms `/terms` (public; linked from every auth page)
- Auth (public; signed-in visitors are redirected to `/collections`). Sign-in is GitHub or Google only (owner decision, 2026-10-28), so there are no password pages
  - Sign in `/sign-in` (one page for new and returning users; `/sign-up` redirects here)
  - Auth callback `/auth/callback` (no UI; completes the provider sign-in and shows the cancelled or failed state if the provider returns an error)
- App (Auth)
  - Collections `/collections`: the home of the app
    - New collection `/collections/new`
    - Collection `/collections/[collectionId]` (redirects to Documents)
      - Documents `/collections/[collectionId]/documents`
      - MCP server `/collections/[collectionId]/server`
      - Playground `/collections/[collectionId]/playground`
      - Activity `/collections/[collectionId]/activity`
      - Course `/collections/[collectionId]/course` (only when course mode is on)
        - Syllabus and concept map `/collections/[collectionId]/course/syllabus`
        - Session digest `/collections/[collectionId]/course/digests/[digestId]`
        - Practice (quizzes, spaced repetition) `/collections/[collectionId]/course/practice`
        - Assignment hints `/collections/[collectionId]/course/hints`
      - Settings `/collections/[collectionId]/settings` (name, mode, rotate or revoke token, delete collection)
  - Account `/account` (name and avatar from the provider, linked sign-in methods, sign-out everywhere, delete account)
- System
  - Not found and error pages (the template's, restyled)
  - `/health` (the template's liveness and readiness)
  - `/sitemap.xml`, `/robots.txt` (public pages only; app and auth pages `noindex`)
- Not pages, but part of the structure
  - **MCP endpoint** `/mcp/[publicId]`: the URL a collection's MCP client calls. It is not served by the Next.js proxy (see "Routing finding" below).
  - API `/v1/...`: the typed backend API, reached from the browser through `/api/*`.

### Routing finding (affects the architecture)

The template's `/api/*` proxy passes only a short list of request headers to the backend and deliberately drops cookies and `Authorization` (`frontend/src/lib/api/proxy.ts`). MCP clients authenticate with an `Authorization: Bearer` token, so `/mcp/*` cannot go through that proxy. It must be routed straight to the backend by the reverse proxy in front of both. This is for the architecture records to settle; the IA assumes `https://sapiduct.olaheavy.dev/mcp/<publicId>` reaches the backend directly.

## Navigation Model

- **Primary navigation (app):** a left rail on wide screens listing the user's collections, with "New collection" at its top and the account menu at its foot. There is no top-level feature menu: the product has one noun, the collection. Maximum visible collections in the rail: the 8 most recently used; "All collections" opens the full list.
- **Secondary navigation:** the collection tab bar: Documents · MCP server · Playground · Activity · (Course) · Settings. At most six tabs. Course appears only in course mode and sits before Settings. The active tab uses a visible state that does not depend on colour alone.
- **Utility navigation:** the user menu (Account, theme toggle, sign out) and a "Connect guides" link in the footer of the rail.
- **Public navigation (landing, demo, guides):** a small top bar: logo, Demo, Guides, Sign in, and a primary "Get started" button. No mega menus.
- **Auth page:** no navigation beyond the logo (back to `/`).
- **Mobile navigation:** the rail becomes a collection switcher in a top bar; the tab bar becomes a horizontally scrollable strip; the account menu moves into the top bar. No hamburger for the five main tabs, since they are the content of the page.
- **Depth:** at most three levels: Collections → Collection → Tab. The Course module adds a fourth level, kept to a side list inside the Course tab and not in the main navigation.

## Content Hierarchy

### Landing `/`
1. The promise and one primary action: a one-sentence headline, "Get started", and "Try the demo" — first, because the evaluator decides in seconds.
2. A real product view: the MCP server tab and a playground result with citations — proof over illustration.
3. The connect snippet shown as text, copyable — shows how little there is to do.
4. How it works in three steps: add documents, connect, ask — the whole product.
5. Course mode (CourseLens) as one section with its own screenshot.
6. Footer: guides, privacy, terms, source repository link.

### Collections `/collections`
1. The collection cards, most recently used first — the thing the user came for.
2. "New collection" as a primary action; the first-run empty state replaces the grid with one centred action and a link to the sample collection.
3. A summary line above the cards only if it carries real figures from the API (collections, documents, calls this week); otherwise omitted.

### Collection → Documents
1. The upload zone with the accepted types and size limit written beside it, then the document list — adding material is the repeated action.
2. A batch strip while an upload is indexing ("18 of 240 left"), so a large upload is one line, not hundreds of moving rows.
3. For a long list: search by name, status chips with counts that come from the server (All, Indexed, Processing, Queued, Failed), a sort, and a cursor pager showing "Showing a to b of N". The list does not reorder under the user while documents finish.
4. Status per document (queued, parsing, indexed, failed with the reason).
5. With the Failed chip selected, one "Retry all failed" action.
6. Row actions (re-index, remove) — secondary, behind a menu.

### Collection → MCP server
1. Server status (running or not) and the URL with a copy button — the answer to "is it up, and where is it".
2. The token area: created time, last used, rotate and revoke; the token value only at creation.
3. Config snippets in tabs (Claude Desktop, Cursor), each with a "last tested" date once tested.
4. The tools this server exposes, with descriptions — a read-only list that links to the Playground.

### Collection → Playground
1. The tool list, with the selected tool's description and input form — where trying starts.
2. The request and result, side by side, with cited passages — the proof.
3. "Show raw" for the JSON-RPC exchange; "Test in MCPJam" link with the copy-paste box.
4. The chat-with-trace panel, once built, as a separate section below, clearly labelled and rate-limited.

### Collection → Activity
1. A live list of recent calls: time, tool, status, latency — answers "is anything using it".
2. Filters: status (success, error), tool, time range.
3. A call's detail on selection: arguments, result size, cited documents.

### Collection → Course (course mode only)
1. The syllabus outline with per-session metadata and progress — the Udemy-style outline without commerce.
2. The next thing to do: due reviews or the next session — drives the learning loop.
3. Concept map, digests, practice and hints as the section's sub-pages.

### Sign in `/sign-in`
1. One line saying there is no password and that signing in creates an account for a new user — so a new visitor knows what will happen.
2. Two buttons of equal weight, Continue with GitHub (primary) and Continue with Google.
3. The failure state: a cancelled or failed provider sign-in returns here with a plain message naming the provider and offering the other one.
4. The brand panel on the right (wide screens only): the annotated sentence and the three steps; it carries no form and no required information.
5. Terms and privacy links at the foot.

## User Flows

### New user to first working connection
1. User lands on `/` and chooses Get started (or Try the demo first).
2. Continue with GitHub or Google at `/sign-in`; the provider returns the user to `/auth/callback`, then `/collections`.
   - If the user cancels or the provider fails → back to `/sign-in` with the failure message.
   - If the same verified email signs in with the other provider → Supabase links the identities automatically; an unverified email is never linked (see the auth record).
3. `/collections` shows the empty state; the user chooses "Create your first collection".
4. `/collections/new`: name, mode (Knowledge by default), then Create.
5. Documents tab opens with the upload zone; the user adds files.
   - If a file type or size is not allowed → rejected before upload, with the limit shown.
   - If parsing fails → that row shows the reason and a retry; other documents continue.
6. When the first document is indexed, a notice offers "Connect your assistant" → MCP server tab.
7. The user copies the token and a snippet into Claude Desktop or Cursor.
8. The first call appears in Activity; the health dot and "last used" update.

### Try before you connect
1. User opens the Playground tab (or `/demo` without signing in).
2. User picks a tool; the form appears from its input schema.
3. User runs it; request, result and cited passages show.
   - If the call errors → the error is shown in full with the raw response.
4. Optional: "Test in MCPJam" opens the hosted tool in a new tab with the copy-paste box.

### Rotate or revoke a token
1. MCP server tab → Rotate token.
2. A dialog names the collection and explains the overlap period; the user confirms.
3. The new token is shown once with a copy button; the old one keeps working for the stated overlap.
   - Revoke: a dialog names the collection; confirming ends access immediately and Activity records the revocation.

### Switch a collection to course mode
1. Settings → Mode → Course; the user confirms.
2. A Course tab appears; its syllabus starts generating from the indexed documents.
   - If there are no indexed documents → the tab shows an empty state with a link to Documents.
3. The user opens the syllabus, a digest, or practice.

### Delete a collection
1. Settings → Delete collection; the dialog states what will be removed (documents, index, token, activity) and asks the user to type the collection's name.
2. On confirm the MCP server stops answering immediately and the user returns to `/collections`.

## Naming Conventions

| Concept | Label in UI | Notes |
|---|---|---|
| A set of documents with one MCP server | Collection | Not "workspace", "project" or "knowledge base": one word everywhere |
| A file or page inside a collection | Document | "Source" is reserved for connectors (URL, Notion) when they ship |
| The hosted endpoint | MCP server | Written "MCP server" in prose; the tab is "MCP server" |
| The secret a client sends | Access token | Never "API key", since it grants access to one collection only |
| Trying tools by hand | Playground | Matches MCPJam's term |
| Record of calls | Activity | Not "logs" (those are the platform's) |
| Reading material becomes a course | Course mode | The module is named CourseLens in marketing and docs |
| Reviewing with spaced repetition | Practice | Not "flashcards" (the module also has quizzes) |
| The guidance on assignments | Hints | Never "solutions" |
| A passage the answer came from | Citation | The chip is labelled with the document and location |

## Component Reuse Map

| Component | Used on | Behavior differences |
|---|---|---|
| App shell (rail, top bar, user menu) | All app pages | Rail collapses to a switcher below 768px |
| Collection tab bar | All collection pages | Course tab appears only in course mode |
| Page header (title, one-line description, primary action) | Collections, each tab, Account | Primary action changes per page |
| Collection card | Collections, rail "All collections" | Rail shows a compact variant |
| Data table | Documents, Activity, Collections (list view later) | Row actions and filters differ; keyset pagination from the template |
| Status badge (word plus icon, not colour alone) | Documents, MCP server, Activity, collection cards | Different state sets |
| Copy field (monospace value and copy button) | MCP server, guides, landing | The token variant is masked after creation |
| Citation chip and passage viewer | Playground, Activity detail, Course | Opens in a side sheet |
| Confirm dialog (names the thing affected) | Revoke, rotate, delete collection, delete account | Typed confirmation for delete only |
| Empty state (one action, optional motif) | Collections, Documents, Activity, Course | Copy and action differ |
| Auth layout (split, brand panel) | All auth pages | Brand panel hidden below 1024px |
| Toast | Everywhere | Polite live region |

## Content Growth Plan

- **Collections per user and documents per collection** are the lists that grow. Both use keyset pagination (the template's `Page[T]`, limits of 1 to 100) with a search field once a list passes one page. A document list shows 25 at a time with a cursor pager rather than page numbers, and its status counts and totals come from the server, never from the rows on screen. A collection's maximum number of documents is a limit for the limits record (issue #5), not decided here.
- **The MCP `list_sources` tool paginates too**: it takes a `limit` (up to a stated maximum) and a `cursor`, and returns the total with a next cursor, so an assistant is never handed a thousand file names at once.
- **Activity** is the fastest-growing list. It is paginated, filterable by status, tool and time, and has a retention period that the architecture records must set; the IA only requires that the screen states the period it keeps.
- **Course content** grows per session; the outline groups by section and collapses completed ones.
- **Public pages** stay small: landing, demo, two connect guides, privacy and terms. New connect guides (other clients) are added under `/docs/connect/[client]`.

## URL Strategy

- **Pattern:** nouns in plural, kebab-case, nested by ownership: `/collections/[collectionId]/[tab]`. No action verbs except `/collections/new` and auth pages (`/sign-in`, `/sign-up`).
- **Identifiers:** `collectionId` in app URLs is the collection's internal id, so renaming a collection never breaks a link. The public MCP URL uses a separate, unguessable `publicId` (a short random string), so the URL does not reveal the id or the name; the access token is still required.
- **Query parameters:** `?status=`, `?tool=`, `?range=` for Activity filters; `?cursor=` and `?limit=` for pagination; `?next=` on auth pages for the post-sign-in return path, accepted only for same-site paths. Nothing personal (email, tokens) ever appears in a URL.
- **Indexing:** public pages are indexable; app, auth and demo-result pages are `noindex`.
- **Redirects:** `/collections/[collectionId]` → `/documents`; signed-in visitors on `/sign-in` → `/collections`; `/sign-up`, `/forgot-password` and `/check-email` → `/sign-in`; signed-out visitors on app pages → `/sign-in?next=...`.
