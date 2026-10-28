# Inspiration Teardown: products Sapiduct learns from

Captured 2026-10-28 in Chrome (desktop window about 1568 px wide, public pages only, no sign-in). Screenshots were taken at 0.6 scale, so small text was not legible; layout and colour observations come from those images. Font, size and colour values come from `getComputedStyle` where listed, and only for MCPJam, Context7 and Supabase. Everything else is visual impression, not measurement. Mobile was not tested. Linear's login page rendered blank and is not covered.

Why these ten: they cover the three things Sapiduct has to do well. Registries and docs-to-MCP products show how to present MCP servers. Developer dashboards and auth pages show the technical shell. Notion and Udemy show how people read and learn from material.

---

## 1. Context7 (context7.com): the directory table

**Essence:** A dense, dark, utilitarian directory of 153,000+ libraries with one job: find docs and copy the MCP command.

**Structure:** Banner, top bar, hero ("Up-to-date docs for AI agents") with an install command box and a copy button, a search field, a Popular/Trending toggle, then a table (name, source repo, token and snippet counts, update time, trust stars), then "Trusted by teams at".

**Measured:** background `rgb(12,10,9)`, text `rgb(231,229,228)`, Inter 16px body, H1 36px / 600 / -0.9px, primary button `rgb(5,150,105)` (emerald) with 8px radius, JetBrains Mono for code.

**Take:** The install command with a copy button sits above the fold, which is where Sapiduct's "connect" snippet belongs. The table is the right pattern for a long document list. Emerald on near-black (a warm stone, not blue-black) works.

**Weakness:** Small grey text on black is hard to read, and the table is dense to the point of tiring.

## 2. Smithery (smithery.ai): the registry, and a warning

**Essence:** A warm, characterful MCP registry. A flame mascot wearing sunglasses, serif display type, orange accent, and cards with usage counts ("22.49k uses") and an "Add to toolbox" button.

**Structure:** Hero "Give agents more agency", a search box, a grid of server cards, a terminal block (`npx smithery auth login`, `npx smithery mcp add notion`), "Publish on Smithery" with observability copy, and a docs call to action.

**A market signal worth recording:** On this visit a dialog read, in full: "Smithery's MCP Proxy and managed identity shut down on October 31. Server URLs on run.tools and server.smithery.ai, the Smithery API, and Smithery accounts stop working that day. smithery.ai stays up as a public MCP registry." The dialog showed no year, so it presumably means this month. I read it directly, but I have not read the linked "what's changing" page, so I don't know why. It suggests a hosted MCP gateway and identity layer was hard to sustain, which is exactly the part of Sapiduct that would cost money to run. Read their explanation before betting on that layer.

**Take:** A personality device (mascot, serif) makes a technical directory memorable. Card metadata (uses, short blurb, one action) is a good pattern for a collection card. A terminal block shows the product in two lines.

**Weakness:** The page loads long card descriptions in full (some run to hundreds of words), which is noisy.

## 3. MCPJam (mcpjam.com): the playground we want to link to

**Essence:** Dark app screenshot as the hero, with a clear promise: "Test your MCP server in every major AI client."

**Structure:** Headline left, an install-command box with copy and platform download buttons (Mac and Windows) on the right, then a large product screenshot showing two models side by side with metrics and charts, and suggested prompt chips under it.

**Measured:** H1 Montserrat 48px / 800 / -1.68px; body Inter 16px; also Instrument Sans and JetBrains Mono; button background `rgb(56,37,28)` (a warm brown), pill radius. The hero colours read as a warm dark with an orange accent.

**Take:** Show the real product in the hero, not an illustration. Side-by-side comparison panels are a strong pattern for the playground. Suggested prompts under the chat reduce the blank-page problem (the website's Ask Sunkanmi uses this too). A pill-shaped primary button on a warm dark palette is a good model for Sapiduct's technical panels.

## 4. Mintlify (mintlify.com): docs as product

**Essence:** Dark, green-accented, with a generative line-art graphic behind a docs-product screenshot. "The intelligent documentation platform."

**Structure:** Centered nav with a sign-in and a white "Get started" pill, headline and subline left, a product screenshot right, a logo wall ("Join 20,000+ of the world's most ambitious companies").

**Take:** A generative line motif is a cheap way to give a dark page identity. For Sapiduct, lines flowing into a duct could be the equivalent. A logo wall is not applicable yet, because Sapiduct has no customers.

## 5. Vercel login (vercel.com/login): the minimal auth page

**Structure:** A single centred column on black. Title "Log in to Vercel", an email field, a white "Continue with Email" primary button, then a stack of equal-width outlined buttons (Google, GitHub, SAML SSO, Passkey), "Show other options", and a sign-up link at the bottom.

**Take:** One column, one primary action, the rest secondary. The email-first step with providers below keeps the page short. The primary button inverts (white on black), so it is the only bright element.

**Weakness:** The page has no explanation of the product, which is fine for a known brand and wrong for a new one.

## 6. Supabase sign-in (supabase.com/dashboard/sign-in): the split auth page

**Structure:** Two columns. Left: logo, "Welcome back", provider buttons (GitHub, a ChatGPT sign-in, SSO) above a divider, then email and password with a "Forgot password?" link, a green "Sign in" button, a sign-up link, and terms text at the bottom. Right: a large customer quote with an avatar.

**Measured:** background `oklch(0.19 0.0025 157.5)` (a near-black with a green tint), text `oklch(0.95 …)`, Inter and Manrope, Source Code Pro for code.

**Take:** The split layout gives the form room and gives the brand a place to speak. For Sapiduct the right panel can show the product, for example a small "your document becomes tools" illustration, in place of a testimonial. A tinted dark that matches the brand colour feels deliberate. Because Sapiduct would use Supabase Auth, the auth flows (provider order, password reset, email verification) map one to one.

## 7. Notion (notion.com): the calm shell

**Structure:** White page, a huge tight sans headline with an inline highlighted word ("Where teams and agents [Think] together."), a short subline, a blue primary and a light secondary button, a large product screenshot with hand-drawn character illustrations around it, and a logo rail.

**Take:** The inline highlighted word is the same device the personal website uses (name in a lilac highlight), so it fits your house style. Hand-drawn touches on a clean shell give warmth. This is the reference for the calm half of the hybrid direction (collections and documents).

## 8. Udemy course page (udemy.com): the learning layout

**Structure:** A dark hero band across the top with breadcrumbs, title, subtitle, rating and instructor. A preview card on the right (video thumbnail with a play button, price and purchase actions) that stays visible while scrolling. Below: "What you'll learn" as a two-column checklist, related topic chips, and an expandable "Course content" outline with section titles and lesson durations. (The right card was still loading in my capture.)

**Take (for CourseLens only):** The expandable outline with per-lesson metadata is the model for the syllabus and the lesson list. A "what you'll learn" checklist suits a generated course summary. Do not copy the commerce pieces (price, cart, reviews, instructor profile): Sapiduct has no marketplace.

## Cross-cutting learnings

1. **Show the real product early.** MCPJam, Mintlify and Notion all put a real screenshot in the hero. Sapiduct's landing page should show a collection and its tools, not a metaphor.
2. **The connect snippet is a first-class element.** Context7, MCPJam and Smithery put a copyable command above the fold. Sapiduct's MCP tab should open with the URL, a token field and one-click config snippets for Claude Desktop and Cursor.
3. **Dark is the default for the technical half, but warm beats blue-black.** Context7 (stone), MCPJam (warm brown, orange) and Smithery (warm, orange) all avoid the cold blue-black of generic dev tools. This supports the hybrid plan: a warm calm shell and warm dark technical panels, with one accent colour.
4. **Auth pages stay short.** One primary action, providers as equal-width secondaries, terms at the bottom. A split layout adds brand space without adding fields.
5. **Metadata on cards earns attention.** Smithery's usage counts and Context7's table columns show what matters. Sapiduct's collection cards should show document count, last indexed time, and calls this week.
6. **Personality in one place.** Smithery's mascot and the website's illustrated self both concentrate personality in one device. Sapiduct needs one: a flow motif (lines or water moving through a duct) used in the logo, empty states, and the loading state of ingestion.
7. **Mind the hosting risk.** The Smithery shutdown notice is the strongest evidence in this teardown that hosted MCP infrastructure is a hard business. Sapiduct should stay lean and measure its own cost from the start.

## Anti-references (carry over from the website, plus)

Generic dark "developer terminal" pages; AI gradient blobs; intro loaders; testimonial walls with no customers; marketplace chrome (prices, carts, reviews) on a product that has none; dense grey-on-black tables with no hierarchy.
