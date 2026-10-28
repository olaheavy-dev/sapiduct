# Design Review: Sapiduct prototype v1

Reviewed against: DESIGN_BRIEF.md
Philosophy: Flow editorial (calm paper shell, warm-dark technical panels, one flow motif)
Date: 2026-10-28
Reviewed: `.design/sapiduct/prototype/index.html`, published page (version 2)

## Screenshots Captured

All viewed on the published page in a desktop browser. **They were not saved into `screenshots/`:** the browser tool used here returns images to the session and cannot write them to a chosen path, so this review lists what was seen instead of linking files.

| View | Theme | What it showed |
| --- | --- | --- |
| Landing | Dark, light | Hero with text left and product panel right; three step cards; course-mode section |
| MCP server tab | Dark | URL, masked token, config snippet, tool list |
| Playground | Dark, light | Tool list and form, empty result panel |
| Collections | Light | Three collection cards and a large empty area |

**Not covered in round 1:** the phone width (375) and tablet width (768). Resizing the window did not change the viewport the in-browser screenshot tool captured, so those widths were unreviewed. Also not seen: documents, activity, course and the auth pages, and any hover, focus, error or loading state. Round 2 (below) fills most of this in with a different capture method.

**Correction (round 2):** while setting up that method I briefly read a clipped phone screenshot of v1 as an overflow bug. It was not: headless Chrome has a minimum window width, so a 375px window renders wider and is then cropped. Phone widths are now captured inside an exact 375px frame, and v1's phone layout was never re-checked that way before it was replaced.

## Summary

The structure and the token system hold up: contrast is good in both themes, the two-column playground logic is sound, and the light landing page, where the dark product panel sits on paper, is the strongest view. But the prototype reads as a competent template, not a considered design. The biggest finding is that nothing in it is specific to Sapiduct beyond its content: the shell is warm paper with a serif and a terracotta accent (a common default look), the signature motif is a generic diagram, several screens are mostly empty, and the controls are default-looking. The owner's reaction, "does not feel refined or like a lot of thought went into it", is accurate.

## Must Fix

1. **Screens open empty or half-empty.** The playground opens with a blank result panel and the one line "Run a tool to see…". The collections page is three small cards at the top and roughly two thirds empty space below, with a stray developer note caption left in. The brief says every screen opens in a realistic working state. _Fix: preload a completed search run in the playground; give the collections page real content (a next-step strip, recent activity across collections, index health) and remove the note._
2. **The signature motif is generic.** Three dotted lines run into an empty rounded box and out to three pills. The box has no meaning, the lines carry no data, and it is a stock "inputs, processor, outputs" diagram. It is the only identity device in the design and it is not distinctive. _Fix: tie the motif to real state (documents by type, indexing progress, tools exposed) or replace it with a device that comes from what the product does, which is showing where an answer came from._
3. **No hierarchy of action.** On the MCP server tab, Copy, Rotate and Revoke share one style, so a destructive action looks like a copy button. In Documents, the upload zone and the table compete. In the playground, "Run tool" is the same size as the secondary link. _Fix: one primary action per screen; a distinct, quieter-until-hover danger style; sizes that follow importance._
4. **Phone and tablet layouts were unverified.** See above. _Fix: capture with a method that sets the viewport exactly before any claim about responsiveness. Done in round 2._

## Should Fix

5. **The shell has no point of view of its own.** Warm paper, a serif display and a terracotta accent is a common default look, and nothing structural sets it apart. The research's own anti-reference list warns against looking generic. _Fix: pick one structural idea that comes from the product and use it everywhere (see "Direction for v2" below)._
6. **The shell and the technical panels barely differ in dark mode.** I raised the panel one step after the first look, but in dark the two worlds are still close in tone, so the hybrid idea only shows in light. _Fix: separate them by more than a shade: a different surface treatment (border, inset, grid texture) rather than only a lighter fill._
7. **Controls look default.** Inputs, selects and tabs are plain; status badges are all the same pill; the two segmented controls and the tab bar are three different treatments for similar jobs. No hover, focus-visible, disabled, loading or error state is shown anywhere. _Fix: design one control family and show its states._
8. **Small, low-contrast labels carry too much.** Uppercase monospace labels at 13px are used for panel titles, column heads and captions, so they compete with each other and are the hardest text on the page to read. _Fix: fewer label styles, larger, and used only where a label earns it._
9. **The landing page has holes and a weak second half.** The hero's left column floats in space beside a busy right panel that combines a result and a diagram; the three step cards are generic; the course-mode section is two lines of text with a link; there is no footer, no repository link and no proof of the product beyond one panel. _Fix: one clear hero idea, a real second section for course mode with its own visual, and a footer with the source link._
10. **Typography is not fully exercised.** Fraunces is set once at weight 600 for headings with no use of its optical size or character; body is fine. There is no deliberate scale in use beyond heading, body and label. _Fix: set a type scale and use display size on one or two moments only._

## Could Improve

11. **Motion** is limited to a toast and one hover lift. Candidate: the single moment where a document becomes a citation.
12. **Copy buttons** change label but not state visibly enough; consider a short check transition.
13. **Keyboard affordances** (shortcuts, visible focus on the segmented controls) were not designed.
14. **Empty, loading and error states** exist only as prose in the brief.

## What Works Well

- **Contrast and tokens.** Both themes pass the checks, the tech tokens behave, and swapping themes needs no component changes.
- **The light landing.** A dark product panel on warm paper is the strongest, most readable composition in the prototype.
- **Citation chips.** Repeating one small element for "where this came from" is the right device for the principle "show the proof". It deserves to be the design's centrepiece.
- **Information structure.** The tab order, the tool list and form layout, the read-only badge on tools (from Smithery), and the auth flow all follow the IA and the research.
- **Honest labelling.** Sample data and illustrative snippets are marked, so nothing in the prototype overclaims.

## Direction for v2

The strongest idea already in the design is the citation: the product's promise is that every answer shows its source. A v2 can be built around that instead of a diagram:

- **Concept: the annotated document.** Treat the interface like a document with margin notes. Citations appear as numbered footnote marks that open their passage in a margin or side sheet; documents, results and course material all use the same mark. The flow motif becomes the line that runs from a numbered mark to its source.
- **One distinctive structural device,** not a decorative one: a ruled or gridded margin rail, a consistent footnote style, and numerals set in the display face.
- **Real content at rest on every screen,** with the states (empty, loading, error, hover, focus) designed and shown.
- **A control family** with a clear primary, a quiet secondary and a distinct danger style.
- **Review loop:** build, capture, critique, adjust, at all three widths in both themes, before showing it.

---

# Round 2: prototype v2 (the annotated document)

Reviewed: `prototype/index.html` (published version 3). Direction chosen by the owner: annotated document.

## Screenshots Captured

Saved in `.design/sapiduct/screenshots/`, captured with headless Chrome. Desktop widths load the page directly; phone widths load it inside an exact 375px frame (the page is 375 CSS pixels wide, the grey strip beside it is the frame's backdrop). The theme is forced with `?theme=light` or `?theme=dark`.

| Screenshot | Width | Theme | Shows |
| --- | --- | --- | --- |
| `v2-landing-light-1280.png` | 1280 | Light | Hero, annotated answer with margin notes, steps, course mode card |
| `v2-landing-light-375.png` | 375 | Light | The same page; notes sit under each statement |
| `v2-collections-light-1280.png` | 1280 | Light | Table-of-contents list with dotted leaders and margin notes, recent calls |
| `v2-documents-dark-375.png` | 375 | Dark | Document list with trace lines and the selected-document panel |
| `v2-mcp-dark-1280.png` | 1280 | Dark | MCP server tab with numbered margin notes |
| `v2-mcp-light-768.png` | 768 | Light | The same tab at tablet width; notes stack with a left rule |
| `v2-playground-light-1280.png` | 1280 | Light | Tool list and form beside a result with marked sources |
| `v2-playground-light-375.png`, `v2-playground-dark-375.png` | 375 | Light, dark | Playground stacked on a phone |
| `v2-activity-dark-1280.png` | 1280 | Dark | Call log with the selected call beside it |
| `v2-course-light-1280.png` | 1280 | Light | Unit rail, due-today card, sessions |
| `v2-signin-light-1280.png`, `v2-signin-dark-1280.png` | 1280 | Light, dark | Sign in with the annotated-sentence panel |
| `v2-states-light-1280.png` | 1280 | Light | Buttons, inputs, badges, trace lines, empty, loading, error, marks, toast |

## What round 1 found, and what changed

| Round 1 finding | Round 2 |
| --- | --- |
| Screens open empty (1) | The playground opens on a completed search; collections gets recent calls; documents opens with a document selected. Fixed. |
| Generic motif (2) | Replaced by the numbered mark and its dotted leader to a margin note, used on every screen. The trace line shows work in progress. Fixed in direction; judge it on the page. |
| No action hierarchy (3) | One control family: primary, secondary, ghost and a distinct danger style that fills on hover (Revoke). Shown on the States screen. Fixed. |
| Phone and tablet unverified (4) | Captured at 375 and 768. No horizontal overflow seen on the screens captured. Fixed for those screens. |
| No point of view (5) | The annotated document is the point of view. The risk remains that it is judged on taste; see below. |
| Shell and panels blur in dark (6) | Panels are now inset (darker than the page in dark, darker still in light) and used only for machine strings and logs. Improved. |
| Default-looking controls (7) | One family with default, hover, focus, disabled, loading and error shown. Improved; hover and focus are forced on the States page and were not exercised with a real pointer or keyboard. |
| Small mono labels (8) | Fewer label styles, larger sizes; mono is used for machine strings. Improved. |
| Landing holes (9) | The annotated answer is the hero; course mode has its own card; footer with the source link. Fixed. |
| Type not exercised (10) | Fraunces carries statements, notes and numerals; marks use the display face. Improved. |

## Found during round 2, and fixed

1. The Result and Raw toggle was unreadable in the light theme (dark text on a dark segment).
2. "Open passage" lost its button styling inside the serif notes.
3. Leader lines also attached to notes nested inside cards; they now attach only to notes that sit beside their statement.
4. The course card on the landing page was too narrow for its titles; it now has a wider column.
5. The collection rail wrapped collection names; it now stacks name and mode.

## Remaining issues

### Should fix
1. **The phone playground is long.** Tools, input and result stack in one column, so the result sits below the fold on a phone. Consider putting the result first after a run, or a sticky "Run" bar.
2. **Query input is a one-line field.** A question longer than the field is cut off. A multi-line field for `query` would read better.
3. **The brand panel on the auth pages is thin.** It shows one annotated sentence beside the form and is empty at the top and bottom. It could carry the three-step explanation or the connect line.
4. **Notes carry a lot of the explanation.** On a phone they land under their block, which works, but on the MCP tab they are the only place the "shown once" token rule is stated. Consider repeating it next to the token field.

### Could improve
5. **Motion** is still limited to the mark lifting on hover, the trace line, and the toast. The one moment worth animating is a mark opening its source.
6. **Not covered:** documents and activity at tablet width, course at 375, reduced motion, keyboard-only use, and the Raw view. Hover and focus were forced, not exercised.
7. **Contrast** relies on the token checks (text secondary on secondary backgrounds, accent text on tinted note backgrounds); the tinted active-note background was not measured.

## What works well

- **The annotated answer.** It shows the product's promise in one view and is the strongest composition in the prototype, in both themes and at both widths.
- **The table-of-contents collection list.** Dotted leaders and margin notes make a simple list distinctive without decoration.
- **Margin notes as help.** Explanations sit beside the field they explain, and fall back under it on narrow screens.
- **Inset only for machine strings.** The URL, token, snippet and logs are the only dark surfaces on the light shell, so the technical half is easy to find.
- **One control family** with its states on a single page.

---

# Round 3: sign-in and large collections

Two owner requests after v2: sign-in by GitHub or Google only, and what happens to a collection with many documents. The owner then reported that the Documents tab looked the same for a large collection, which was right: the large view sat behind a prototype switch and defaulted off.

- **Sign-in:** the password pages are gone. One page, `/sign-in`, offers Continue with GitHub and Continue with Google, says plainly that signing in creates an account, and has a designed cancelled or failed state (`v3-signin-light-1280.png`). The brand panel carries the three steps.
- **Large collection is now the default** for Physics notes (1,284 documents); the 14-document view is one click away. The Documents tab was redesigned for it (`v4-documents-light-1280.png`, `v4-documents-dark-375.png`):
  - Search, sort and an Add documents button in one toolbar, with status chips and counts that add up (1,254 + 13 + 6 + 11 = 1,284).
  - A column layout on desktop (name, type, size, status) with a select-all box, and a two-line layout on phones where names wrap instead of truncating.
  - Row selection with a bulk bar (Re-index, Remove, Clear), and Retry all failed when the Failed chip is chosen.
  - A cursor pager, 25 at a time, and a note that the list does not jump while documents finish.
  - A batch strip for a large upload, one line instead of hundreds of moving rows.
  - Rejected files are summarised in one collapsed line with the reasons inside (a 148 MB file over the limit, an unsupported video).
  - A very large single document (842 pages, 21.4 MB) shows determinate progress, "reading page 312 of 842", and says that pages 1 to 311 are already searchable.
  - On phones and tablets the selected document's detail opens inline under its row instead of in a panel far below the list.
- **Tested:** a scripted run in headless Chrome clicked the status chips (25 rows to 11), the search box, Next (rows 26 to 50), the checkboxes (bulk bar shows 2 selected) and the size switch (5 rows in the small view). It found a real bug, a variable named `view` that shadowed a function, which broke every interaction after the first render; fixed.
- **Limits not decided:** the maximum documents per collection, the maximum upload size and the page-size maximums are for the limits record (issue #5). The 25 MB figure in the prototype is a sample.
- **Not covered:** the Activity list at scale, drag-and-drop anywhere on the page (the Add documents button toasts), keyboard use of the bulk bar, and a virtualized list (25 rows per page makes it unnecessary for now).

---

# Round 4: the finished prototype (v5)

The owner asked to finish the prototype and asked whether there was a chat playground to test the tools. There was not (it was specified last, issue #24), so it was added.

## What was added

- **Chat playground with trace:** a second playground mode, "Chat with a model" (`v5-playground-chat-light-1280.png`, `v5-playground-chat-dark-375.png`). The model's tool calls show inline with the tool, its arguments, a success or error badge, a summary and the latency, and the answer carries numbered source marks. It also has suggested prompts, a message budget (8 of 20, sample), a rate limit message, an error call, and a daily-limit state that points back to calling tools by hand or bringing an API key. No real model runs; replies are canned and labelled so.
- **Create collection** with validation and a mode choice (`v5-new-collection-light-1280.png`), and the **empty collection** state across Documents, MCP server, Playground and Activity (`v5-documents-empty-light-1280.png`). Adding documents shows each file's check (ready, too large), then indexing, then "your server is running".
- **Collection settings** (`v5-settings-light-1280.png`): rename, switch Knowledge or Course (the Course tab appears and disappears), and delete with a typed confirmation.
- **Dialogs** built on the native dialog element (focus moves in, Escape closes, focus returns): rotate token (shows the new token once), revoke token (the token row changes to "No active token"), delete collection, delete account, add documents, and a **passage side sheet** opened from "Open passage" (`v5-dialog-revoke-light-1280.png`).
- **Account** (`v5-account-light-1280.png`): name and avatar from the provider, sign-in methods, sign out everywhere, delete account.
- **Activity at scale** (`v5-activity-dark-1280.png`): 848 sample calls over 30 days, range chips with counts (Today 38, 7 days 212, 30 days 848), status and tool filters, a cursor pager (25 at a time) and a selected-call panel. The 7-day count matches the "212 calls this week" shown on the collections page.
- **Course:** a **practice** flow with six questions, answer checking, a cited explanation and a summary with the next review (`v5-practice-light-1280.png`); a session **digest** with cited statements; and an assignment **hints** page with three levels that never give the full solution.
- **Public pages:** a **connect guide** page (`v5-guides-light-1280.png`) that says "last tested: not yet tested" until a client is tested, a read-only **demo** route, a **first-run** empty collections state (`v5-collections-first-run-light-1280.png`), and a **404** page (`v5-404-light-1280.png`).
- A skip-to-content link, and the whole screen list in the prototype banner.

## How it was checked

- A scripted run in headless Chrome drove every flow and reported no page errors: first-run toggle, create-collection validation and creation, adding documents and watching them index, renaming, switching mode, the typed-confirmation delete dialogs, rotate and revoke, chat (reply with tool call, rate limit, budget running out and the limit message), activity ranges, filters, paging and a simulated call (7 days 212 to 213), practice to its summary, three hints and the disabled button, account deletion, the demo route, the guide client switch, unknown routes going to the 404 page, and the `sign-up` alias going to sign-in. The passage sheet opens as a side sheet.
- Screens were captured at 1280 and, for the chat and documents, at an exact 375px frame, in light and dark.

## Not covered

- Real pointer and keyboard use: the script used programmatic clicks and events. Tab order, focus rings on every new control, and dialog focus trapping were not tested with a keyboard.
- Screen-reader output of the live regions (the chat log, the practice feedback, the hint list).
- Reduced motion on the new screens.
- Tablet width (768) for the new screens, and phone width for practice, hints, settings and account.
- The playground chat is canned: it cannot show how a real model behaves with these tools, how long answers read, or how errors look when a model misuses a tool.
- The hash-based demo and not-found routes are prototype devices; the real build uses real URLs (see the IA).
