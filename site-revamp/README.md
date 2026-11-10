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
6. SEO lengths in `content/seo.json` itself: title at most 60, description 120–160.
7. Keywords: every page has a set for its language, 8 or more, emitted verbatim, and
   no keyword appears on more than three pages.
8. `hreflang`: all three links on every page, each pointing at the right counterpart.
9. Structured data: the required types per page, `inLanguage` on each, and the FAQ
   JSON-LD mirroring the visible questions exactly.
10. Primary terms: every page's visible text uses each of its `primary` terms.
11. Machine-readable files: `llms.txt` and both `security.txt` copies exist, name the
    real host, and keep the RFC 9116 shape.
12. Sitemap shape: every page in both languages, nothing else.
13. Alt text on every image.
14. JSON-LD parses on every page.
15. Every sitemap URL has a file.
16. `og.png` is exactly 1200×630.
17. Every colour in the static CSS is a token, and every `var()` is defined.
18. Contrast: every text and UI token pair meets WCAG 2.2 AA.
19. Word counts per page, from the rendered `main`.
20. Language: every page has a counterpart in both languages.
21. Reference counts: tools, prompts, resources and commands equal the real definitions.
22. Diagrams: `role="img"`, `<title>` and `<desc>` on every SVG.
23. Claims: every page has claims, every evidence path exists, every status is valid.
24. Legal texts on every page and the NOTICE verbatim on the license pages.

## Structure

```
content/site.json          URL, lastmod, licence, legal texts
content/seo.json           per-page title, description, keywords, primary terms, llms line
content/pages/*.json       one file per page, both languages
content/diagrams.json      diagram labels, both languages
templates/                 base.html, page.html, 404.html
diagrams/*.svg.j2          diagram templates, rendered per language
static/                    style.css, site.js, favicon.svg, og.png
design-tokens.json         every colour, font, space and radius
design-system/DECISIONS.md the design record and the contrast table
```

`content/seo.json` holds the metadata for both languages, keyed by page id. The home
pages use its `site` block, the 404 its `not_found` block, and every other page its
`pages` block. A page with no block fails the build, so a new page cannot ship
unoptimised. `llms.txt` and `security.txt` are generated from the same data.

The output goes only to `docs/`. The 12 product Markdown files already in `docs/` are
sources and are left untouched.
