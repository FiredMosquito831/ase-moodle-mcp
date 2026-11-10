# Design decisions — ase-moodle docs site

## Identity

The product is a terminal tool for students: an MCP server, a CLI and a plugin. The site
borrows the old site's blue accent (`#1f6feb`) and turns it into a dark-first "student
terminal" identity: a dark background, monospace command surfaces, a `>` prompt marker on
every section heading, and status pills for read / write / local tools. The old site was a
single light page with the same blue; the accent is the one thing carried over.

Dark-first is a deliberate choice: the product is used from a terminal and from coding
agents, and the old site's light page had no second theme.

## Design intelligence tool

The `ui-ux-pro-max` design tool was not run for this build. The site is plain HTML and CSS
with no framework and no Tailwind, and the palette had a verified source in the old site
(`site/index.html`, `theme-color` `#1f6feb`). The system below is hand-built from that
accent and labelled as a fallback.

## Adopted

- Dark background `#0A0E14`, surfaces `#111722` and `#17202D`, text `#E8EEF6`, muted `#A7B6C9`.
- Accent `#5B9DFF` for text and links (7.10:1 on the background); the old `#1F6FEB` stays as
  the fill of primary buttons and the brand mark, with white text (4.63:1).
- System fonts only: `system-ui` for prose, `ui-monospace` for commands and labels. No
  external font, CDN, analytics or embed.
- A 1120 px maximum width, a 68ch measure for prose, a sticky table of contents above 1024 px.
- Cards with a 3 px accent top border; facts as a grid of token cards; diagrams on a surface panel.
- Status colours: success `#3FB950`, warning `#D29922`, error `#F85149`.
- A print stylesheet: no header, footer or table of contents, readable measure, expanded
  external links, page breaks before headings.

## Rejected

- A light theme. The product has no light UI to derive one from, and a second theme doubles
  the contrast surface for no verified benefit.
- A centred hero with three identical cards and a gradient blob. The site is a documentation
  surface; the front door is the command block and the harness diagram.
- A search box. The site is static and has no search index; a box that does not search would
  be a dead control.
- A carousel. Nothing essential is hidden behind interaction.
- Screenshots of a product UI. There is no product UI; the diagrams and real command output
  carry the page.

## Contrast (WCAG 2.2 AA, computed from the final tokens)

| Foreground | Background | Ratio | Minimum | Result |
|---|---|---:|---:|---|
| text | bg | 16.57:1 | 4.5:1 | pass |
| text | surface | 15.38:1 | 4.5:1 | pass |
| text | surface-2 | 14.05:1 | 4.5:1 | pass |
| text-muted | bg | 9.37:1 | 4.5:1 | pass |
| text-muted | surface | 8.70:1 | 4.5:1 | pass |
| accent | bg | 7.10:1 | 4.5:1 | pass |
| accent | surface | 6.59:1 | 4.5:1 | pass |
| accent-contrast (white) | accent-strong | 4.63:1 | 4.5:1 | pass |
| success | bg | 7.61:1 | 4.5:1 | pass |
| warning | bg | 7.66:1 | 4.5:1 | pass |
| error | bg | 5.77:1 | 4.5:1 | pass |
| border | bg | 3.56:1 | 3:1 | pass |
| border | surface | 3.30:1 | 3:1 | pass |
| focus | bg | 9.09:1 | 3:1 | pass |
| text | code-bg | 15.96:1 | 4.5:1 | pass |

Lowest body pair: white on `#1F6FEB`, 4.63:1. Lowest UI pair: border on surface, 3.30:1.
The builder recomputes this table on every run and fails below the thresholds.

## Language

Romanian is the primary language: `x-default` points at the Romanian page. The old site
pointed `x-default` at English; the owner's decision is Romanian-first, so the default
follows the primary language. Every page declares `hreflang` for `ro`, `en` and `x-default`,
and the language switch links the exact counterpart page, not the home page.

## Site source

The existing `site/` is the previous generated output and stays read-only. The new source
lives in `site-revamp/` and the new output in `docs/`, as the brief requires. The builder
writes only its own generated paths; the 12 product Markdown files in `docs/` are untouched.
