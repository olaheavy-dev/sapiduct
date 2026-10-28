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

**Not covered:** the phone width (375) and tablet width (768). Resizing the window did not change the viewport the screenshot tool captured, so those widths are unreviewed. Also not seen: documents, activity, course and the auth pages (they were checked only in code), and any hover, focus, error or loading state.

## Summary

The structure and the token system hold up: contrast is good in both themes, the two-column playground logic is sound, and the light landing page, where the dark product panel sits on paper, is the strongest view. But the prototype reads as a competent template, not a considered design. The biggest finding is that nothing in it is specific to Sapiduct beyond its content: the shell is warm paper with a serif and a terracotta accent (a common default look), the signature motif is a generic diagram, several screens are mostly empty, and the controls are default-looking. The owner's reaction, "does not feel refined or like a lot of thought went into it", is accurate.

## Must Fix

1. **Screens open empty or half-empty.** The playground opens with a blank result panel and the one line "Run a tool to see…". The collections page is three small cards at the top and roughly two thirds empty space below, with a stray developer note caption left in. The brief says every screen opens in a realistic working state. _Fix: preload a completed search run in the playground; give the collections page real content (a next-step strip, recent activity across collections, index health) and remove the note._
2. **The signature motif is generic.** Three dotted lines run into an empty rounded box and out to three pills. The box has no meaning, the lines carry no data, and it is a stock "inputs, processor, outputs" diagram. It is the only identity device in the design and it is not distinctive. _Fix: tie the motif to real state (documents by type, indexing progress, tools exposed) or replace it with a device that comes from what the product does, which is showing where an answer came from._
3. **No hierarchy of action.** On the MCP server tab, Copy, Rotate and Revoke share one style, so a destructive action looks like a copy button. In Documents, the upload zone and the table compete. In the playground, "Run tool" is the same size as the secondary link. _Fix: one primary action per screen; a distinct, quieter-until-hover danger style; sizes that follow importance._
4. **Phone and tablet layouts are unverified.** See above. _Fix: capture with a tool that can set the viewport, or ask the owner for phone screenshots, before any claim about responsiveness._

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
