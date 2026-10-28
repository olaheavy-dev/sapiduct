# Build Tasks: Sapiduct

Generated from: .design/sapiduct/DESIGN_BRIEF.md (+ INFORMATION_ARCHITECTURE.md, DESIGN_TOKENS.css)
Date: 2026-10-28

Codebase scan (`frontend/` and `backend/` as generated from house-template-nextjs v0.3.0 and house-template-fastapi v0.6.1):
- **Frontend:** no `components/` directory, no icon or UI library, no app routes beyond a placeholder `page.tsx`, `/health`, error pages and the `/api/*` proxy. Conventions to adopt from the first task: Next.js App Router, strict TypeScript, `src/` layout, components in `src/components/<area>/PascalCase.tsx`, kebab-case routes, co-located `*.test.tsx` (Vitest and Testing Library), Playwright for e2e, axe and screenshots (already part of `make check`).
- **Backend:** FastAPI app with `GET /v1/me`, keyset pagination, an `authenticate()` hook that fails closed in production, SQLAlchemy and Alembic on two branches (template and `app`), pgvector, S3-compatible storage with presigned URLs, and the budget-capped model gateway with embeddings.
- **Tokens:** `frontend/src/styles/tokens.css` is the neutral starter; `DESIGN_TOKENS.css` replaces its values and adds the missing categories (first task).

Aesthetic for every task: **Flow editorial**: warm paper and ink shell, terracotta accent, a warm-dark tech surface for the server, playground and activity panels, and one flow motif that moves only during real activity (see the brief).

How the repo's rules apply (AGENTS.md): every task becomes a GitHub issue with a plan and acceptance criteria before it is built; one branch per issue; PRs squash-merged through review. Tasks marked 🔑 need a new dependency or a spending or infrastructure change, so they need the owner's approval first.

Legend: ⚠ risk-first item · 🔑 needs owner approval · 🧪 feeds back to the house templates

## Foundation

- [ ] **Tokens, fonts and theme, live on the landing hero** _(visual priority first)_: Replace the starter values in `tokens.css` with `DESIGN_TOKENS.css`, load Fraunces, Geist and Geist Mono with `next/font`, add a no-flash theme toggle (system default, persisted), and rebuild the placeholder home as the landing hero: headline, "Get started" and "Try the demo" actions, and a connect-snippet block. Done = both themes render without flash, every existing e2e and axe test still passes, screenshots regenerated, and the owner has seen the aesthetic. _Modifies: `tokens.css`, `layout.tsx`, `page.tsx`. New: `ThemeToggle`, `CopyField`._ 🔑 (confirm Fraunces licence and loading cost)
- [ ] **⚠ Architecture records**: Write and get accepted: data model and tenant isolation (user → collections → documents; one MCP server per collection), MCP routing and auth (FastMCP mounted in the backend; `/mcp/*` bypasses the Next proxy because that proxy drops `Authorization`; access tokens hashed at rest, rotation overlap), ingestion pipeline (upload, sandboxed parsing, chunking, embedding, queue or worker), auth provider (Supabase Auth, verification behind `authenticate()`), limits and abuse controls (free-tier limits, rate limits per token, activity retention period, playground chat budget). Done = records `0003` onwards in `docs/decisions/`, accepted by the owner, each naming what it rules out. _No components._
- [ ] **⚠ Tenant isolation spike**: Collections and documents tables with an owner id, every query scoped by the signed-in user, and tests proving user B cannot read, list, change or delete user A's collections through any endpoint. Done = the cross-tenant tests fail without the scoping and pass with it. _Reuses: `SessionDep`, `CurrentUser`, keyset `Page[T]`. New: models, migration on the `app` branch, `/v1/collections`._ 🧪 (a tenant-scoping helper is a template candidate)
- [ ] **⚠ MCP endpoint spike**: FastMCP mounted at `/mcp/{publicId}` with a `search` tool over stub data, bearer token resolved to one collection, stateless HTTP, routed past the Next proxy in Compose. Done = a real MCP client lists the tool and calls it with a valid token; a wrong or revoked token and another collection's token are refused; the same test passes through Compose's front door. _New: `app/mcp/`._ 🔑 (adds `fastmcp`; pin the version)
- [ ] **⚠ Ingestion spike**: Presigned upload, then a worker that parses one Markdown, one PDF, one Word and one VTT file in a sandbox, chunks with section and timestamp metadata, embeds under the gateway's budget and stores vectors and full text for hybrid search with citations. Done = on a small openly licensed corpus, a query returns cited passages; a malformed or hostile file fails that one document without stopping others; the spend appears in `make llm-report`. _Reuses: `storage.py`, `gateway.embeddings()`. New: worker, parsers, `documents` and `chunks` tables._ 🔑 (parsers, and a queue or worker decision)
- [ ] **Auth with Supabase and the auth pages**: Verify Supabase's tokens in `authenticate()` (still fails closed without them), and build sign in, sign up, forgot password, reset password and check-your-email in the split layout, with inline errors that never reveal whether an email exists, and a same-site-only `?next=`. Done = the brief's auth flows work end to end against a test project, are keyboard-operable, pass axe in both themes, and `make check` stays green. _Reuses: `frontend/src/lib/auth.ts`, tokens. New: `AuthLayout`, `AuthForm`, `ProviderButtons`, `Field`._ 🔑 (Supabase client dependency, and the free-tier limits to verify)
- [ ] **App shell and collections**: Left rail with the collection switcher, top bar, user menu, the Collections page with cards, the first-run empty state, and the create-collection flow. Done = a signed-in user creates, lists and opens collections; the empty state shows one action and the sample collection link; responsive rail-to-switcher behaviour works. _New: `AppShell`, `Rail`, `PageHeader`, `CollectionCard`, `EmptyState`, `StatusBadge`._

## Core UI

- [ ] **Documents tab**: Upload zone (with a real button, and the accepted types and size limit written beside it), the document table with status per row (queued, parsing, indexed, failed with a reason), retry and remove, and the ingestion progress with the flow motif. Covers: empty, uploading, parsing, partial failure, all indexed. _Depends on: ingestion spike, app shell. New: `UploadZone`, `DocumentTable`, `FlowMotif`._
- [ ] **MCP server tab**: URL with copy, status, token created once and then masked, rotate (with the overlap) and revoke dialogs naming the collection, Claude Desktop and Cursor snippets, and the read-only tool list. Done = a real client connects using only what the tab shows; revoke takes effect immediately. _Depends on: MCP endpoint spike. Reuses: `CopyField`. New: `TokenPanel`, `ConfigSnippets`, `ConfirmDialog`._
- [ ] **Playground: tool list and manual call**: Tools read from the server's `tools/list`, a form generated from each tool's JSON schema, request and result side by side with cited passages, "Show raw", and the "Test in MCPJam" link with the copy-paste box. Covers: no tools, call error, slow call, large result. _Depends on: MCP endpoint spike. New: `ToolList`, `SchemaForm`, `ResultView`, `CitationChip`, `PassageSheet`._ 🔑 (a JSON-schema form library, or hand-built)
- [ ] **Activity tab**: Recent calls table with status, tool and range filters, live arrival of new calls (the motif pulses once per call), and a detail view with arguments, result size and cited documents. States the retention period it keeps. _Depends on: MCP endpoint spike. Reuses: `DocumentTable` (shared data table)._
- [ ] **Settings and Account**: Collection name and mode, token controls, delete collection with typed confirmation; account email, password, sign out everywhere, delete account. Done = every destructive action names what will be removed and has a regression test. _Reuses: `ConfirmDialog`._
- [ ] **Landing page, demo and guides**: The full landing (real product view, connect snippet, how it works in three steps, the course-mode section), `/demo` against a read-only sample collection built from openly licensed documents, `/docs/connect/claude-desktop` and `/docs/connect/cursor`, privacy and terms. Done = every figure shown is sourced; "works with Claude Desktop and Cursor" appears only after each connection was tested and dated. _Depends on: playground, MCP server tab._

## Course mode (CourseLens)

- [ ] **Course tab and syllabus**: Mode switch in Settings, the Course tab, and a syllabus outline with per-session metadata and progress generated from indexed documents, every claim citing a passage. Covers: no indexed documents, generation in progress, generation failed. _Depends on: ingestion spike. New: `CourseOutline`._
- [ ] **Session digests**: A digest page per session with cited bullets. _Reuses: `CitationChip`._
- [ ] **Practice**: Quizzes with spaced repetition, due-today queue, progress. Covers: nothing due, mid-session resume. _New: `QuizCard`, `ReviewQueue`._
- [ ] **Assignment hints**: Socratic hints that never give a full solution, enforced and tested by an eval. _Reuses: the model gateway; evals in `tests/evals/`._

## Interactions & States

- [ ] **Flow motif and motion pass**: Finalise the motif as a component used in ingestion, activity and empty states; static under reduced motion; announced politely where it carries meaning. Covers: idle, active, reduced motion. _Reuses: `FlowMotif`._
- [ ] **Empty, loading and error states pass**: One written pattern per screen, checked in light and dark. _Reuses: `EmptyState`, the template's error pages._
- [ ] **Tool-selection evals in CI**: MCPJam's SDK or CLI runs cases like "for this question the agent should call `search` with these arguments" against a test server and gates merges. Done = a failing case fails CI. 🔑 (adds `@mcpjam/sdk` or the CLI as a dev dependency) 🧪
- [ ] **Playground chat with trace** _(last)_: The model picks tools; each call, its arguments and result show inline; rate-limited per user and under the model gateway's budget. Covers: budget reached, rate-limited, tool error. 🔑 (spending)
- [ ] **Connectors**: URL or `llms.txt` crawl first, then Notion, each with its own brief section. 🔑

## Responsive & Polish

- [ ] **Responsive pass**: Check every screen at 375, 768, 1024 and 1280px against the brief: rail to switcher, playground columns stacking, mobile support level for the playground.
- [ ] **Accessibility pass**: WCAG 2.2 AA on every page; keyboard operation of upload, tabs, tool form, copy buttons and dialogs with focus return; status never by colour alone; live regions for ingestion and streaming; reduced motion. Done = axe clean with no CSP violations, and a manual keyboard run recorded.
- [ ] **Dark mode and performance pass**: Both themes checked on every screen; a performance budget set in an architecture record and enforced in CI.

## Review

- [ ] **Design review**: Run /design-review against the brief once the first slices are built.

## Template findings log (proof-test notes)

Recorded as the build goes; each becomes a `template-candidate` change where it applies to every project.

- The Next `/api/*` proxy drops `Authorization`, so token-authenticated routes (MCP) must bypass it. _(found 2026-10-28 in the IA phase)_
- house-template-nextjs' palette test is unaware of non-starter colour names (the `--color-tech-*` set); it compares light and dark key sets. _(found in the tokens phase)_
- house-template-base's README table still calls the fastapi and nextjs layers "planned" though both are released. _(found 2026-10-28)_
- The frontend needs Node 26 and pnpm 12; this machine has Node 24 and pnpm 11, so `make check` for the frontend has not yet run locally. The backend's `make check-fastapi` passed (177 tests).
