# Site source

The new site source. `scripts/build_site.py` renders it into `docs/`. The existing `site/`
is the previous output and is not read or written by this builder.

## Rebuild

```sh
python -m pip install --requirement requirements-site.txt
python scripts/build_site.py
python scripts/build_site.py --check
```

`--check` renders in memory and compares every generated file with `docs/` byte for byte.
`--report` prints the word count of every page and the reference counts. `--claims` prints
the claims ledger in Markdown.

## Generated from the product

| Part | Source |
|---|---|
| Tools, prompts, resources | `src/ase_moodle/mcp_server.py` (`@mcp.tool`, `@mcp.prompt`, `@mcp.resource`) |
| CLI commands and options | `src/ase_moodle/cli.py` (`build_parser`) |
| Harness names and scopes | `src/ase_moodle/harnesses/` |
| Version | `pyproject.toml` |
| NOTICE | `NOTICE`, verbatim |

The builder fails if a real tool or command has no description, if a description names
something that no longer exists, or if the rendered count differs from the source count.

## Gates

The builder runs these before writing anything. Each one is proven to fail on a broken input.

1. Secret scan over `site-revamp/` and the generated output.
2. Forbidden-string scan over the same files.
3. External-request scan: no remote script, stylesheet, `@import`, `url(http…)` or iframe.
4. Link check: every internal `href` and `src` resolves; every fragment resolves.
5. Page metadata: one `h1`, title at most 60 characters, description 120–160, unique.
6. Alt text on every image.
7. JSON-LD parses on every page.
8. Every sitemap URL has a file.
9. `og.png` is exactly 1200×630.
10. Every colour in the static CSS is a token, and every `var()` is defined.
11. Contrast: every text and UI token pair meets WCAG 2.2 AA.
12. Word counts per page, from the rendered `main`.
13. Language: every page has a counterpart, `hreflang` for `ro`, `en` and `x-default`.
14. Reference counts: tools, prompts, resources and commands equal the real definitions.
15. Diagrams: `role="img"`, `<title>` and `<desc>` on every SVG.
16. Claims: every page has claims, every evidence path exists, every status is valid.
17. Legal texts on every page and the NOTICE verbatim on the license pages.

## Structure

```
content/site.json          URL, lastmod, licence, legal texts
content/pages/*.json       one file per page, both languages
content/diagrams.json      diagram labels, both languages
templates/                 base.html, page.html, 404.html
diagrams/*.svg.j2          diagram templates, rendered per language
static/                    style.css, site.js, favicon.svg, og.png
design-tokens.json         every colour, font, space and radius
design-system/DECISIONS.md the design record and the contrast table
```

The output goes only to `docs/`. The 12 product Markdown files already in `docs/` are
sources and are left untouched.
