#!/usr/bin/env python3
"""Build the ase-moodle documentation site into docs/.

Deterministic: no wall clock, no git history, no randomness, no environment-dependent
output. Every list is ordered by the content files or sorted. The builder writes only
the generated paths under docs/; the product Markdown files in docs/ are read-only
sources and are never touched.

Usage:
    python scripts/build_site.py            # write docs/
    python scripts/build_site.py --check    # compare docs/ with a fresh build
    python scripts/build_site.py --report   # word counts and reference counts
    python scripts/build_site.py --claims   # print the claims ledger (Markdown)
"""

from __future__ import annotations

import argparse
import ast
import html
import json
import re
import struct
import sys
import tokenize
from io import StringIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent.parent
SITE_SRC = ROOT / "site-revamp"
CONTENT = SITE_SRC / "content"
TEMPLATES = SITE_SRC / "templates"
STATIC = SITE_SRC / "static"
DOCS = ROOT / "docs"
PRODUCT = ROOT / "src" / "ase_moodle"

LANGS = ("ro", "en")
OTHER = {"ro": "en", "en": "ro"}
LANG_LABEL = {"ro": "Română", "en": "English"}
LANG_SHORT = {"ro": "RO", "en": "EN"}
HTML_LANG = {"ro": "ro", "en": "en"}

# Pages that get TechArticle structured data: the guide and reference pages.
TECH_ARTICLE_PAGES = ("install", "quick-start", "commands", "tools", "guides", "troubleshooting")

# --------------------------------------------------------------------------- helpers


def die(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
    return {}


def t(value, lang: str) -> str:
    """A translated string: either {"ro": ..., "en": ...} or a plain string."""
    if isinstance(value, dict):
        if lang not in value:
            die(f"missing {lang} translation in {value!r}")
        return value[lang]
    return value


DIACRITICS = str.maketrans("ăâîșțşţĂÂÎȘȚŞŢ", "aaiststAAISTST")


def slug(text: str) -> str:
    s = text.translate(DIACRITICS).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"


INLINE_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
INLINE_CODE = re.compile(r"`([^`]+)`")
INLINE_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def inline(text: str) -> Markup:
    """Escape, then apply the three allowed inline marks: `code`, **bold**, [text](href)."""
    s = html.escape(text, quote=False)
    s = INLINE_CODE.sub(lambda m: f"<code>{m.group(1)}</code>", s)
    s = INLINE_BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", s)
    s = INLINE_LINK.sub(
        lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', s
    )
    return Markup(s)


def md_plain(text: str) -> str:
    """The text a reader sees: inline markers are markup, not content."""
    return text.replace("`", "").replace("**", "")


def words_in_html(fragment: str) -> int:
    text = re.sub(r"<script.*?</script>", " ", fragment, flags=re.S)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return len([w for w in re.split(r"\s+", text) if w.strip()])


def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        die("og.png: not a PNG file")
    return struct.unpack(">II", data[16:24])


def contrast_ratio(fg: str, bg: str) -> float:
    def lum(colour: str) -> float:
        colour = colour.lstrip("#")
        channels = [int(colour[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


# ------------------------------------------------------------------- source extraction

def _const(node) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _kw(call: ast.Call, name: str):
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_attr(node, var: str, attr: str) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == attr and isinstance(node.value, ast.Name) and node.value.id == var


def _first_sentence(text: str) -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""
    match = re.match(r"(.+?\.)(?=\s+[A-Z(]|$)", text)
    return match.group(1) if match else text


def _params(node: ast.FunctionDef) -> list[dict]:
    out = []
    args = node.args
    positional = [*args.posonlyargs, *args.args]
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    for arg, default in zip(positional, defaults):
        if arg.arg in ("self", "cls"):
            continue
        out.append(
            {
                "name": arg.arg,
                "type": ast.unparse(arg.annotation) if arg.annotation else "",
                "default": ast.unparse(default) if default is not None else None,
            }
        )
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        out.append(
            {
                "name": arg.arg,
                "type": ast.unparse(arg.annotation) if arg.annotation else "",
                "default": ast.unparse(default) if default is not None else None,
            }
        )
    return out


def extract_tools() -> list[dict]:
    src = (PRODUCT / "mcp_server.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    tools = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and getattr(dec.func, "attr", None) == "tool":
                kind = "read"
                ann = _kw(dec, "annotations")
                if isinstance(ann, ast.Name):
                    kind = {"READ": "read", "WRITE": "write", "LOCAL": "local"}.get(ann.id, "read")
                tools.append(
                    {
                        "name": node.name,
                        "kind": kind,
                        "params": _params(node),
                        "doc": ast.get_docstring(node) or "",
                        "summary": _first_sentence(ast.get_docstring(node) or ""),
                    }
                )
    return tools


def extract_prompts() -> list[dict]:
    src = (PRODUCT / "mcp_server.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    out = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and getattr(dec.func, "attr", None) == "prompt":
                out.append(
                    {
                        "name": node.name,
                        "params": _params(node),
                        "doc": ast.get_docstring(node) or "",
                        "summary": _first_sentence(ast.get_docstring(node) or ""),
                    }
                )
    return out


def extract_resources() -> list[dict]:
    src = (PRODUCT / "mcp_server.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    out = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and getattr(dec.func, "attr", None) == "resource":
                uri = _const(dec.args[0]) if dec.args else None
                out.append(
                    {
                        "uri": uri or "",
                        "name": node.name,
                        "doc": ast.get_docstring(node) or "",
                        "summary": _first_sentence(ast.get_docstring(node) or ""),
                    }
                )
    return out


def extract_harness_scopes() -> tuple[str, ...]:
    src = (PRODUCT / "harnesses" / "base.py").read_text(encoding="utf-8")
    match = re.search(r'^SCOPES = \(([^)]*)\)', src, re.M)
    return tuple(re.findall(r'"([^"]+)"', match.group(1))) if match else ("global", "project")


def extract_harness_names() -> list[str]:
    init = (PRODUCT / "harnesses" / "__init__.py").read_text(encoding="utf-8")
    tree = ast.parse(init)
    classes: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple):
            names = [
                elt.func.id
                for elt in node.elts
                if isinstance(elt, ast.Call) and isinstance(elt.func, ast.Name)
            ]
            if names:
                classes = names
                break
    out = []
    for cls in classes:
        for path in sorted((PRODUCT / "harnesses").glob("*.py")):
            src = path.read_text(encoding="utf-8")
            if f"class {cls}" in src:
                match = re.search(r'^\s+name = "([^"]+)"', src, re.M)
                if match:
                    out.append(match.group(1))
                break
    return out


OPTION_HINTS = {
    "project_dir": "DIR",
    "out": "DIR",
    "search": "TEXT",
    "subject": "TEXT",
    "text": "TEXT",
    "file": "FILE",
    "answers": "JSON",
    "answers_file": "FILE",
    "json_params": "JSON",
    "filter": "REGEX",
    "pattern": "REGEX",
    "function": "NAME",
    "source": "SOURCE",
    "token": "TOKEN",
    "base_url": "URL",
    "tip": "TIP",
    "ay": "AN",
}


def _option_from_call(call: ast.Call, dicts: dict[str, ast.Dict]) -> dict | None:
    flags = [_const(a) for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
    if not flags:
        return None
    kwargs = {kw.arg: kw.value for kw in call.keywords if kw.arg}
    for kw in call.keywords:
        if kw.arg is None and isinstance(kw.value, ast.Name) and kw.value.id in dicts:
            node = dicts[kw.value.id]
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    kwargs.setdefault(key.value, value)
    dest = flags[0].lstrip("-").replace("-", "_")
    action = _const(kwargs["action"]) if "action" in kwargs else None
    hint = None
    if action in ("store_true", "store_false"):
        hint = None
    elif "choices" in kwargs and isinstance(kwargs["choices"], (ast.List, ast.Tuple)):
        values = [_const(e) for e in kwargs["choices"].elts]
        hint = "|".join(values) if all(values) else OPTION_HINTS.get(dest, dest.upper())
    elif "metavar" in kwargs:
        hint = _const(kwargs["metavar"])
    elif "type" in kwargs and ast.unparse(kwargs["type"]) == "int":
        hint = "N"
    elif flags[0].startswith("--"):
        hint = OPTION_HINTS.get(dest, dest.upper())
    nargs = _const(kwargs["nargs"]) if "nargs" in kwargs else None
    if flags[0].startswith("--"):
        label = flags[0] + (f" {hint}" if hint else "")
    else:
        label = flags[0] + ("..." if nargs in ("*", "+") else "")
    return {"label": label, "flag": flags[0]}


def _helper_options(func: ast.FunctionDef, param: str) -> list[ast.Call]:
    calls = []
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument":
            if isinstance(node.func.value, ast.Name) and node.func.value.id == param:
                calls.append(node)
    return calls


def extract_commands() -> list[dict]:
    tree = ast.parse((PRODUCT / "cli.py").read_text(encoding="utf-8"))
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    helpers = {}
    for name in ("_add_course_filters", "_add_answers", "add_scope"):
        fn = funcs.get(name)
        if fn and fn.args.args:
            helpers[name] = _helper_options(fn, fn.args.args[0].arg)
    build = funcs["build_parser"]
    dicts = {}
    for node in ast.walk(build):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Dict):
            dicts[node.targets[0].id] = node.value

    commands: list[dict] = []
    by_var: dict[str, dict] = {}

    def add_command(name: str, help_text: str | None, var: str | None = None, kind: str = "command") -> dict:
        cmd = {"name": name, "help": help_text or "", "options": [], "kind": kind}
        commands.append(cmd)
        if var:
            by_var[var] = cmd
        return cmd

    def add_options(var: str | None, calls: list[ast.Call]) -> None:
        cmd = by_var.get(var) if var else None
        if not cmd:
            return
        for call in calls:
            opt = _option_from_call(call, dicts)
            if opt and opt["flag"] not in [o["flag"] for o in cmd["options"]]:
                cmd["options"].append(opt)

    def walk(stmts: list[ast.stmt]) -> None:
        for node in stmts:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                call = node.value
                var = node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
                if _is_attr(call.func, "sub", "add_parser"):
                    add_command(_const(call.args[0]) or "?", _const(_kw(call, "help")), var)
                elif _is_attr(call.func, "hsub", "add_parser"):
                    pass
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                func = call.func
                if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                    if func.attr == "add_argument":
                        add_options(func.value.id, [call])
                elif isinstance(func, ast.Attribute) and func.attr == "set_defaults" and isinstance(func.value, ast.Call) and _is_attr(func.value.func, "sub", "add_parser"):
                    inner = func.value
                    add_command(_const(inner.args[0]) or "?", _const(_kw(inner, "help")))
                elif isinstance(func, ast.Name) and func.id in helpers:
                    var = call.args[0].id if call.args and isinstance(call.args[0], ast.Name) else None
                    add_options(var, helpers[func.id])
            elif isinstance(node, ast.For):
                iter_src = ast.unparse(node.iter)
                if "REGISTRY" in iter_src:
                    actions: list[str] = []
                    harness_options: list[dict] = []
                    for inner in ast.walk(node):
                        if isinstance(inner, ast.For) and isinstance(inner.iter, ast.Tuple):
                            actions = [_const(e) or "" for e in inner.iter.elts]
                        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) and inner.func.attr == "add_argument":
                            opt = _option_from_call(inner, dicts)
                            if opt and opt["flag"] not in [o["flag"] for o in harness_options]:
                                harness_options.append(opt)
                    for harness in extract_harness_names():
                        cmd = add_command(harness, f"{harness}: install, update, uninstall, doctor", kind="harness")
                        cmd["actions"] = actions
                        cmd["options"] = [dict(option) for option in harness_options]
                        for option in cmd["options"]:
                            if option["flag"] == "--scope":
                                option["label"] = "--scope " + "|".join((*extract_harness_scopes(), "all"))
                else:
                    walk(node.body)
    walk(build.body)
    return commands


# --------------------------------------------------------------------------- site model

def load_site() -> dict:
    site = load_json(CONTENT / "site.json")
    for key in ("name", "url", "lastmod", "repo", "author", "author_url", "license", "legal"):
        if key not in site:
            die(f"site.json: missing {key}")
    return site


def load_seo() -> dict:
    """The curated per-page SEO data, keyed by page id and language.

    Every page that has a path in both languages needs an entry. The 404 is
    excluded: it is noindex, bilingual and outside the sitemap.
    """
    seo = load_json(CONTENT / "seo.json")
    for key in ("site", "pages"):
        if key not in seo:
            die(f"seo.json: missing {key}")
    for lang in LANGS:
        block = seo["site"].get(lang)
        if not block:
            die(f"seo.json: missing site/{lang}")
        for key in ("title", "description", "keywords", "primary"):
            if not block.get(key):
                die(f"seo.json: site/{lang} missing {key}")
    return seo


def seo_for(seo: dict, page: dict, lang: str) -> dict:
    """The SEO block for one page in one language; a page without one fails."""
    if page["id"] == "home":
        return seo["site"][lang]
    if page["id"] == "404":
        return seo["not_found"][lang]
    block = seo["pages"].get(page["id"], {}).get(lang)
    if not block:
        die(f"seo.json: no {lang} block for page {page['id']!r}")
    for key in ("title", "description", "keywords", "primary"):
        if not block.get(key):
            die(f"seo.json: {page['id']}/{lang} missing {key}")
    return block


def load_pages() -> list[dict]:
    pages = []
    for path in sorted((CONTENT / "pages").glob("*.json")):
        page = load_json(path)
        page["_file"] = path.name
        for key in ("id", "path", "title", "description", "h1", "blocks", "claims"):
            if key not in page:
                die(f"{path.name}: missing {key}")
        pages.append(page)
    pages.sort(key=lambda p: (p.get("order", 999), p["id"]))
    return pages


def substitute(value, values: dict[str, str]):
    """Replace {version}, {tools}, ... in every string of a content tree."""
    if isinstance(value, dict):
        return {key: substitute(item, values) for key, item in value.items()}
    if isinstance(value, list):
        return [substitute(item, values) for item in value]
    if isinstance(value, str):
        for key, replacement in values.items():
            value = value.replace("{" + key + "}", replacement)
        return value
    return value


def page_url(site: dict, path: str) -> str:
    return site["url"].rstrip("/") + path


def canonical_path(path: str) -> str:
    if path.endswith(".html"):
        return path
    return path if path.endswith("/") else path + "/"


def footer_links(pages: list[dict], lang: str) -> list[dict]:
    links = []
    for page in pages:
        if page["id"] == "404":
            continue
        if page["id"] == "home":
            label = "Acasă" if lang == "ro" else "Home"
        elif page.get("nav"):
            label = t(page["nav"], lang)
        else:
            label = t(page["h1"], lang)
        links.append({"href": page["path"][lang], "label": label})
    return links


def build_nav(pages: list[dict], lang: str, current_id: str) -> list[dict]:
    nav = []
    for page in pages:
        if not page.get("nav"):
            continue
        nav.append(
            {
                "href": page["path"][lang],
                "label": t(page["nav"], lang),
                "current": page["id"] == current_id,
            }
        )
    return nav


def section_id(heading: str, used: set[str]) -> str:
    base = slug(heading)
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}-{index}"
        index += 1
    used.add(candidate)
    return candidate


def render_blocks(page: dict, lang: str, ctx: dict) -> tuple[Markup, list[dict]]:
    """Render the page blocks. Returns (html, toc entries)."""
    out: list[str] = []
    toc: list[dict] = []
    used: set[str] = set()
    for block in page["blocks"]:
        kind = block["type"]
        heading = t(block["heading"], lang) if block.get("heading") else None
        sid = section_id(heading, used) if heading else None
        if heading:
            toc.append({"id": sid, "label": heading})
        if kind == "lead":
            out.append(f'<p class="lead">{inline(t(block["text"], lang))}</p>')
        elif kind == "actions":
            items = []
            for item in block["items"]:
                cls = "btn btn-primary" if item.get("kind") == "primary" else "btn"
                items.append(f'<a class="{cls}" href="{t(item["href"], lang)}">{inline(t(item["label"], lang))}</a>')
            out.append(f'<p class="actions">{" ".join(items)}</p>')
        elif kind == "prose":
            body = "".join(f"<p>{inline(t(p, lang))}</p>" for p in block["paragraphs"])
            out.append(_section(sid, heading, body))
        elif kind == "list":
            tag = "ol" if block.get("ordered") else "ul"
            items = "".join(f"<li>{inline(t(i, lang))}</li>" for i in block["items"])
            out.append(_section(sid, heading, f'<{tag} class="plain-list">{items}</{tag}>'))
        elif kind == "cards":
            cards = []
            for item in block["items"]:
                title = inline(t(item["title"], lang))
                href = t(item["href"], lang) if item.get("href") else None
                if href:
                    title = f'<a href="{href}">{title}</a>'
                meta = f'<p class="card-meta">{inline(t(item["meta"], lang))}</p>' if item.get("meta") else ""
                cards.append(f'<li class="card"><h3>{title}</h3><p>{inline(t(item["text"], lang))}</p>{meta}</li>')
            out.append(_section(sid, heading, f'<ul class="cards">{"".join(cards)}</ul>'))
        elif kind == "steps":
            steps = []
            for item in block["items"]:
                code = ""
                if item.get("code"):
                    code = f'<pre><code>{html.escape(item["code"])}</code></pre>'
                steps.append(f'<li><h3>{inline(t(item["title"], lang))}</h3><p>{inline(t(item["text"], lang))}</p>{code}</li>')
            out.append(_section(sid, heading, f'<ol class="steps">{"".join(steps)}</ol>'))
        elif kind == "code":
            label = t(block["label"], lang) if block.get("label") else "shell"
            caption = f'<figcaption>{inline(t(block["caption"], lang))}</figcaption>' if block.get("caption") else ""
            out.append(
                _section(
                    sid,
                    heading,
                    f'<figure class="code"><div class="code-head"><span>{inline(label)}</span></div>'
                    f'<pre><code>{html.escape(block["text"])}</code></pre>{caption}</figure>',
                )
            )
        elif kind == "table":
            head = "".join(f"<th scope=\"col\">{inline(t(h, lang))}</th>" for h in block["headers"])
            rows = "".join(
                "<tr>" + "".join(f"<td>{inline(t(cell, lang))}</td>" for cell in row) + "</tr>"
                for row in block["rows"]
            )
            caption = f'<caption>{inline(t(block["caption"], lang))}</caption>' if block.get("caption") else ""
            out.append(
                _section(
                    sid,
                    heading,
                    f'<div class="table-wrap"><table>{caption}<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>',
                )
            )
        elif kind == "figure":
            diagram = block["diagram"]
            source = f"/assets/diagrams/{diagram}-{lang}.svg"
            out.append(
                _section(
                    sid,
                    heading,
                    f'<figure class="diagram"><img src="{source}" alt="{html.escape(t(block["alt"], lang), quote=True)}" width="960" height="540" loading="lazy">'
                    f'<figcaption>{inline(t(block["caption"], lang))}</figcaption></figure>'
                    f'<p class="figure-alt">{inline(t(block["alt"], lang))}</p>',
                )
            )
        elif kind == "faq":
            items = "".join(
                f'<div class="faq-item"><h3>{inline(t(item["q"], lang))}</h3><p>{inline(t(item["a"], lang))}</p></div>'
                for item in block["items"]
            )
            out.append(_section(sid, heading, f'<div class="faq">{items}</div>'))
        elif kind == "notice":
            notice = (ROOT / "NOTICE").read_text(encoding="utf-8").rstrip("\n")
            caption = f'<figcaption>{inline(t(block["caption"], lang))}</figcaption>' if block.get("caption") else ""
            out.append(
                _section(
                    sid,
                    heading,
                    f'<figure class="code"><div class="code-head"><span>NOTICE</span></div>'
                    f'<pre class="notice">{html.escape(notice)}</pre>{caption}</figure>',
                )
            )
        elif kind == "callout":
            tone = block.get("kind", "note")
            title = f'<p class="callout-title">{inline(t(block["title"], lang))}</p>' if block.get("title") else ""
            out.append(f'<aside class="callout callout-{tone}">{title}<p>{inline(t(block["text"], lang))}</p></aside>')
        elif kind == "facts":
            items = "".join(
                f"<div><dt>{inline(t(item['label'], lang))}</dt><dd>{inline(t(item['value'], lang))}</dd></div>"
                for item in block["items"]
            )
            out.append(_section(sid, heading, f'<dl class="facts">{items}</dl>'))
        elif kind == "generated":
            what = block["what"]
            if what == "tools":
                out.append(render_tools(page, lang, ctx))
            elif what == "commands":
                out.append(render_commands(page, lang, ctx))
            else:
                die(f"{page['id']}: unknown generated block {what!r}")
        else:
            die(f"{page['id']}: unknown block type {kind!r}")
    return Markup("\n".join(out)), toc


def _section(sid: str | None, heading: str | None, body: str) -> str:
    if heading:
        return f'<section id="{sid}"><h2><span class="prompt" aria-hidden="true">&gt;</span> {inline(heading)}</h2>{body}</section>'
    return f"<section>{body}</section>"


KIND_LABEL = {
    "ro": {"read": "citire", "write": "scriere", "local": "local"},
    "en": {"read": "read", "write": "write", "local": "local"},
}
KIND_CLASS = {"read": "tag-read", "write": "tag-write", "local": "tag-local"}


def _params_html(params: list[dict]) -> str:
    if not params:
        return "—"
    parts = []
    for param in params:
        text = f"{param['name']}: {param['type']}" if param["type"] else param["name"]
        if param["default"] not in (None, "None"):
            text += f" = {param['default']}"
        parts.append(f"<code>{html.escape(text)}</code>")
    return " ".join(parts)


def _check_coverage(page: dict, section: str, real: list[str], names: list[str]) -> None:
    if len(names) != len(set(names)):
        die(f"{page['id']}: duplicate names in {section}")
    missing = sorted(set(real) - set(names))
    extra = sorted(set(names) - set(real))
    if missing:
        die(f"{page['id']}: {section} missing from content: {', '.join(missing)}")
    if extra:
        die(f"{page['id']}: {section} names not in the source: {', '.join(extra)}")


def render_tools(page: dict, lang: str, ctx: dict) -> str:
    data = page.get("tools") or die(f"{page['id']}: missing tools data")
    tools = ctx["tools"]
    by_name = {tool["name"]: tool for tool in tools}
    grouped: list[str] = []
    seen: list[str] = []
    for group in data["groups"]:
        names = group["names"]
        seen.extend(names)
        rows = []
        for name in names:
            tool = by_name[name]
            desc = t(data["descriptions"][name], lang) if lang == "ro" else tool["summary"]
            rows.append(
                f'<tr id="tool-{name}"><td><code>{name}</code></td>'
                f'<td><span class="tag {KIND_CLASS[tool["kind"]]}">{KIND_LABEL[lang][tool["kind"]]}</span></td>'
                f"<td>{_params_html(tool['params'])}</td><td>{inline(desc)}</td></tr>"
            )
        heading = t(group["label"], lang)
        grouped.append(
            f'<section id="tools-{group["id"]}"><h2><span class="prompt" aria-hidden="true">&gt;</span> {inline(heading)}</h2>'
            f'<div class="table-wrap"><table><thead><tr><th>{"Unealtă" if lang == "ro" else "Tool"}</th>'
            f'<th>{"Tip" if lang == "ro" else "Type"}</th><th>{"Parametri" if lang == "ro" else "Parameters"}</th>'
            f'<th>{"Ce face" if lang == "ro" else "What it does"}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>'
        )
    _check_coverage(page, "tools", [tool["name"] for tool in tools], seen)
    for name in [tool["name"] for tool in tools]:
        if lang == "ro" and name not in data["descriptions"]:
            die(f"{page['id']}: missing ro description for tool {name}")

    prompts = ctx["prompts"]
    prompt_rows = []
    for prompt in prompts:
        desc = t(data["prompts"][prompt["name"]], lang) if lang == "en" else prompt["summary"]
        prompt_rows.append(
            f'<tr id="prompt-{prompt["name"]}"><td><code>{prompt["name"]}</code></td>'
            f"<td>{_params_html(prompt['params'])}</td><td>{inline(desc)}</td></tr>"
        )
    _check_coverage(page, "prompts", [p["name"] for p in prompts], list(data["prompts"]))
    resources = ctx["resources"]
    resource_rows = []
    for resource in resources:
        desc = t(data["resources"][resource["uri"]], lang) if lang == "en" else resource["summary"]
        resource_rows.append(
            f'<tr id="resource-{slug(resource["uri"])}"><td><code>{resource["uri"]}</code></td><td>{inline(desc)}</td></tr>'
        )
    _check_coverage(page, "resources", [r["uri"] for r in resources], list(data["resources"]))

    labels = {
        "ro": ("Prompturi", "Resurse", "Prompt", "Parametri", "Ce face", "Resursă", "Conținut"),
        "en": ("Prompts", "Resources", "Prompt", "Parameters", "What it does", "Resource", "Content"),
    }[lang]
    return (
        "\n".join(grouped)
        + f'<section id="tools-prompts"><h2><span class="prompt" aria-hidden="true">&gt;</span> {labels[0]}</h2>'
        f'<div class="table-wrap"><table><thead><tr><th>{labels[2]}</th><th>{labels[3]}</th><th>{labels[4]}</th></tr></thead>'
        f'<tbody>{"".join(prompt_rows)}</tbody></table></div></section>'
        f'<section id="tools-resources"><h2><span class="prompt" aria-hidden="true">&gt;</span> {labels[1]}</h2>'
        f'<div class="table-wrap"><table><thead><tr><th>{labels[5]}</th><th>{labels[6]}</th></tr></thead>'
        f'<tbody>{"".join(resource_rows)}</tbody></table></div></section>'
    )


def render_commands(page: dict, lang: str, ctx: dict) -> str:
    data = page.get("commands") or die(f"{page['id']}: missing commands data")
    commands = ctx["commands"]
    by_name = {cmd["name"]: cmd for cmd in commands}
    grouped: list[str] = []
    seen: list[str] = []
    for group in data["groups"]:
        names = group["names"]
        seen.extend(names)
        rows = []
        for name in names:
            cmd = by_name[name]
            if cmd["kind"] == "harness":
                desc = t(data["en"][name], "en") if lang == "en" else cmd["help"]
                options = " ".join(f"<code>{html.escape(a)}</code>" for a in cmd["actions"])
                options += " " + " ".join(f"<code>{html.escape(o['label'])}</code>" for o in cmd["options"])
                rows.append(
                    f'<tr id="cmd-{name}"><td><code>ase-moodle {name}</code></td><td>{options}</td><td>{inline(desc)}</td></tr>'
                )
            else:
                desc = t(data["en"][name], "en") if lang == "en" else cmd["help"]
                options = " ".join(f"<code>{html.escape(o['label'])}</code>" for o in cmd["options"]) or "—"
                rows.append(
                    f'<tr id="cmd-{name}"><td><code>ase-moodle {name}</code></td><td>{options}</td><td>{inline(desc)}</td></tr>'
                )
        heading = t(group["label"], lang)
        grouped.append(
            f'<section id="commands-{group["id"]}"><h2><span class="prompt" aria-hidden="true">&gt;</span> {inline(heading)}</h2>'
            f'<div class="table-wrap"><table><thead><tr><th>{"Comandă" if lang == "ro" else "Command"}</th>'
            f'<th>{"Opțiuni" if lang == "ro" else "Options"}</th><th>{"Ce face" if lang == "ro" else "What it does"}</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>'
        )
    _check_coverage(page, "commands", [cmd["name"] for cmd in commands], seen)
    for name in [cmd["name"] for cmd in commands]:
        if name not in data["en"]:
            die(f"{page['id']}: missing en description for command {name}")
    return "\n".join(grouped)


# --------------------------------------------------------------------------- diagrams

def tool_surface_svg(tools: list[dict], groups: list[dict], lang: str) -> str:
    """Generate the tool-surface diagram from the real tool definitions."""
    labels = {
        "ro": {"title": "Suprafața uneltelor MCP", "desc": f"{len(tools)} de unelte, grupate pe zone, cu tipul fiecăreia: citire, scriere sau local.", "total": "unelte", "read": "citire", "write": "scriere", "local": "local", "legend": "Legendă"},
        "en": {"title": "The MCP tool surface", "desc": f"{len(tools)} tools, grouped by area, with each one's type: read, write or local.", "total": "tools", "read": "read", "write": "write", "local": "local", "legend": "Legend"},
    }[lang]
    kinds = {name: kind for name, kind in [(t["name"], t["kind"]) for t in tools]}
    colours = {"read": "#3FB950", "write": "#D29922", "local": "#5B9DFF"}
    width, height = 960, 540
    rows = []
    top = 96
    for index, group in enumerate(groups):
        y = top + index * 58
        names = group["names"]
        counts = {k: sum(1 for n in names if kinds[n] == k) for k in ("read", "write", "local")}
        dots = []
        x = 470
        for kind in ("read", "write", "local"):
            for _ in range(counts[kind]):
                dots.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{colours[kind]}"/>')
                x += 18
        label = t(group["label"], lang)
        rows.append(
            f'<text x="48" y="{y + 5}" class="label">{html.escape(label)}</text>'
            f'<text x="360" y="{y + 5}" class="count">{len(names)}</text>'
            + "".join(dots)
        )
    legend = (
        f'<g class="legend"><text x="48" y="486" class="legend-title">{labels["legend"]}</text>'
        f'<circle cx="140" cy="481" r="6" fill="{colours["read"]}"/><text x="154" y="486" class="legend-text">{labels["read"]}</text>'
        f'<circle cx="222" cy="481" r="6" fill="{colours["write"]}"/><text x="236" y="486" class="legend-text">{labels["write"]}</text>'
        f'<circle cx="312" cy="481" r="6" fill="{colours["local"]}"/><text x="326" y="486" class="legend-text">{labels["local"]}</text></g>'
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="ts-title ts-desc" class="diagram-svg">
  <title id="ts-title">{labels["title"]}</title>
  <desc id="ts-desc">{labels["desc"]}</desc>
  <style>
    .bg {{ fill: #0A0E14; }}
    .frame {{ fill: #111722; stroke: #5A6B82; stroke-width: 1; }}
    .label {{ fill: #E8EEF6; font: 500 17px system-ui, sans-serif; }}
    .count {{ fill: #A7B6C9; font: 600 16px ui-monospace, Consolas, monospace; }}
    .total {{ fill: #5B9DFF; font: 700 30px ui-monospace, Consolas, monospace; }}
    .total-label {{ fill: #A7B6C9; font: 500 15px system-ui, sans-serif; }}
    .legend-title {{ fill: #A7B6C9; font: 600 13px system-ui, sans-serif; text-transform: uppercase; letter-spacing: .08em; }}
    .legend-text {{ fill: #E8EEF6; font: 400 14px system-ui, sans-serif; }}
  </style>
  <rect class="bg" width="{width}" height="{height}" rx="16"/>
  <rect class="frame" x="16" y="16" width="{width - 32}" height="{height - 32}" rx="12"/>
  <text x="48" y="58" class="total">{len(tools)}</text>
  <text x="48" y="78" class="total-label">{labels["total"]}</text>
  {''.join(rows)}
  {legend}
</svg>
'''


# --------------------------------------------------------------------------- build

def build(site: dict, pages: list[dict], ctx: dict) -> dict[str, bytes]:
    tokens = load_json(SITE_SRC / "design-tokens.json")
    seo = load_seo()
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["inline"] = inline
    env.globals["t"] = t
    output: dict[str, bytes] = {}

    def put(rel: str, data: str | bytes) -> None:
        output[rel] = data.encode("utf-8") if isinstance(data, str) else data

    css = render_css(tokens)
    put("assets/style.css", css)
    put("assets/site.js", (STATIC / "site.js").read_text(encoding="utf-8"))
    put("assets/favicon.svg", (STATIC / "favicon.svg").read_text(encoding="utf-8"))
    diagrams = load_json(CONTENT / "diagrams.json")
    diagram_env = Environment(
        loader=FileSystemLoader(str(SITE_SRC / "diagrams")),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    for template_path in sorted((SITE_SRC / "diagrams").glob("*.svg.j2")):
        name = template_path.name[: -len(".svg.j2")]
        template = diagram_env.get_template(template_path.name)
        for lang in LANGS:
            if name not in diagrams or lang not in diagrams[name]:
                die(f"diagrams.json: missing {name}/{lang}")
            put(f"assets/diagrams/{name}-{lang}.svg", template.render(labels=diagrams[name][lang], lang=lang))
    tool_groups = next((p["tools"]["groups"] for p in pages if p["id"] == "tools"), [])
    for lang in LANGS:
        put(f"assets/diagrams/tool-surface-{lang}.svg", tool_surface_svg(ctx["tools"], tool_groups, lang))
    og = (STATIC / "og.png").read_bytes()
    put("og.png", og)
    put("CNAME", site["url"].split("//", 1)[1].rstrip("/") + "\n")
    put("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {site['url'].rstrip('/')}/sitemap.xml\n")

    page_by_id = {page["id"]: page for page in pages}
    sitemap_entries = []
    for page in pages:
        for lang in LANGS:
            path = page["path"].get(lang)
            if not path:
                continue
            if page["id"] == "404":
                continue
            other = page["path"].get(OTHER[lang])
            hreflangs = [
                {"lang": "ro", "href": page_url(site, page["path"]["ro"])},
                {"lang": "en", "href": page_url(site, page["path"]["en"])},
                {"lang": "x-default", "href": page_url(site, page["path"]["ro"])},
            ]
            blocks_html, toc = render_blocks(page, lang, ctx)
            canonical = page_url(site, canonical_path(path))
            jsonld = build_jsonld(site, page, lang, canonical, seo_for(seo, page, lang))
            template = env.get_template("page.html")
            body = template.render(
                site=site,
                page=page,
                lang=lang,
                meta=seo_for(seo, page, lang),
                other_lang=OTHER[lang],
                other_path=page["path"][OTHER[lang]],
                lang_short=LANG_SHORT[OTHER[lang]],
                lang_label=LANG_LABEL[OTHER[lang]],
                nav=build_nav(pages, lang, page["id"]),
                nav_label="Navigare" if lang == "ro" else "Navigation",
                home=page["path"][lang] if page["id"] == "home" else ("/" if lang == "ro" else "/en/"),
                canonical=canonical,
                hreflangs=hreflangs,
                blocks=blocks_html,
                toc=toc,
                jsonld=jsonld,
                tokens=tokens,
                footer_pages=footer_links(pages, lang),
            )
            rel = path.lstrip("/")
            if rel == "":
                rel = "index.html"
            elif rel.endswith("/"):
                rel += "index.html"
            put(rel, body)
            sitemap_entries.append(
                {
                    "loc": canonical,
                    "lastmod": site["lastmod"],
                    "priority": page.get("priority", "0.5"),
                    "hreflangs": hreflangs,
                }
            )

    # 404: one bilingual page, noindex, not in the sitemap.
    page404 = page_by_id["404"]
    template404 = env.get_template("404.html")
    body404 = template404.render(
        site=site,
        page=page404,
        lang="ro",
        meta=seo["not_found"]["ro"],
        other_lang="en",
        other_path=None,
        lang_short="EN",
        lang_label="English",
        noindex=True,
        canonical=None,
        hreflangs=[],
        jsonld="",
        tokens=tokens,
        nav=build_nav(pages, "ro", "404"),
        nav_label="Navigare",
        home="/",
        footer_pages=footer_links(pages, "ro"),
    )
    put("404.html", body404)

    put("sitemap.xml", render_sitemap(site, sitemap_entries))
    put("llms.txt", render_llms(site, pages, seo, ctx))
    put("security.txt", render_security(site))
    put(".well-known/security.txt", render_security(site))
    return output


def render_css(tokens: dict) -> str:
    lines = [":root {"]
    for group, values in tokens.items():
        if not isinstance(values, dict):
            continue
        for name, value in values.items():
            lines.append(f"  --{group}-{name}: {value};")
    lines.append("}")
    lines.append("")
    lines.append((STATIC / "style.css").read_text(encoding="utf-8"))
    return "\n".join(lines)


def build_jsonld(site: dict, page: dict, lang: str, canonical: str, meta: dict) -> str:
    blocks = [
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": meta["title"],
            "url": canonical,
            "description": meta["description"],
            "inLanguage": HTML_LANG[lang],
            "isPartOf": {"@type": "WebSite", "name": site["name"], "url": site["url"]},
        }
    ]
    if page["id"] != "home":
        blocks.append(
            {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Acasă" if lang == "ro" else "Home", "item": page_url(site, page["path"][lang] if page["id"] == "home" else ("/" if lang == "ro" else "/en/"))},
                    {"@type": "ListItem", "position": 2, "name": t(page["h1"], lang), "item": canonical},
                ],
            }
        )
    if page["id"] == "home":
        blocks.append(
            {
                "@context": "https://schema.org",
                "@type": "WebSite",
                "name": site["name"],
                "url": page_url(site, page["path"][lang]),
                "inLanguage": HTML_LANG[lang],
                "description": meta["description"],
            }
        )
        blocks.append(
            {
                "@context": "https://schema.org",
                "@type": "SoftwareApplication",
                "name": site["name"],
                "alternateName": "ase-moodle-mcp",
                "description": meta["description"],
                "applicationCategory": "DeveloperApplication",
                "operatingSystem": "Windows, Linux",
                "softwareVersion": site["version"],
                "inLanguage": HTML_LANG[lang],
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
                "license": site["license"]["url"],
                "isAccessibleForFree": True,
                "codeRepository": site["repo"],
                "author": {"@type": "Person", "name": site["author"], "url": site["author_url"]},
            }
        )
    if page["id"] in TECH_ARTICLE_PAGES:
        blocks.append(
            {
                "@context": "https://schema.org",
                "@type": "TechArticle",
                "headline": meta["title"],
                "name": meta["title"],
                "url": canonical,
                "inLanguage": HTML_LANG[lang],
                "description": meta["description"],
                "about": {"@type": "SoftwareApplication", "name": site["name"], "url": site["url"]},
                "proficiencyLevel": "Beginner" if page["id"] in ("install", "quick-start") else "Expert",
                "author": {"@type": "Person", "name": site["author"], "url": site["author_url"]},
                "isPartOf": {"@type": "WebSite", "name": site["name"], "url": site["url"]},
            }
        )
    if page["id"] == "faq":
        faq_blocks = [b for b in page["blocks"] if b["type"] == "faq"]
        if faq_blocks:
            blocks.append(
                {
                    "@context": "https://schema.org",
                    "@type": "FAQPage",
                    "inLanguage": HTML_LANG[lang],
                    "mainEntity": [
                        {
                            "@type": "Question",
                            "name": md_plain(t(item["q"], lang)),
                            "acceptedAnswer": {"@type": "Answer", "text": md_plain(t(item["a"], lang))},
                        }
                        for block in faq_blocks
                        for item in block["items"]
                    ],
                }
            )
    return json.dumps(blocks, ensure_ascii=False, indent=2)


def render_llms(site: dict, pages: list[dict], seo: dict, ctx: dict) -> str:
    """llms.txt: a Markdown map of the site, absolute links, one line each."""
    base = site["url"].rstrip("/")
    values = {
        "version": site["version"],
        "tools": str(len(ctx["tools"])),
        "prompts": str(len(ctx["prompts"])),
        "resources": str(len(ctx["resources"])),
        "commands": str(len(ctx["commands"])),
    }

    def line(page_id: str, lang: str) -> str:
        page = next(p for p in pages if p["id"] == page_id)
        block = seo_for(seo, page, lang)
        summary = block.get("llms")
        if not summary:
            die(f"seo.json: {page_id}/{lang} has no llms line")
        summary = substitute(summary, values)
        return f"- [{block['title']}]({page_url(site, page['path'][lang])}): {summary}"

    out = [
        "# ase-moodle",
        "",
        "> Server MCP, CLI și plugin pentru Moodle BL@ASE (online.ase.ro); an MCP server, CLI and plugin for BL@ASE Moodle.",
        "",
        f"ase-moodle opens a BL@ASE Moodle account at online.ase.ro inside Claude Code, Codex, "
        f"opencode and Google Antigravity: courses, materials, assignments, forums, grades, quizzes "
        f"and deadlines. It is an independent Apache-2.0 project, version {site['version']}, not "
        f"affiliated with ASE Bucharest or Moodle. Everything runs on the user's machine; writes "
        f"need explicit confirmation. The site is Romanian-first, with a full English version under /en/.",
        "",
        "## Română",
        "",
        line("home", "ro"),
        line("install", "ro"),
        line("commands", "ro"),
        line("tools", "ro"),
        line("guides", "ro"),
        line("faq", "ro"),
        line("license", "ro"),
        "",
        "## English",
        "",
        line("home", "en"),
        line("install", "en"),
        line("commands", "en"),
        line("tools", "en"),
        line("guides", "en"),
        line("faq", "en"),
        line("license", "en"),
        "",
        "## Optional",
        "",
        f"- [Sursa / source]({site['repo']}): the repository, the product documentation in docs/*.md and the issue tracker.",
        f"- [Sitemap]({base}/sitemap.xml): every page in both languages.",
    ]
    return "\n".join(out) + "\n"


def security_expires(site: dict) -> str:
    """Within one year of lastmod, in RFC 3339. From site.json, never the clock."""
    from datetime import date, timedelta

    start = date.fromisoformat(site["lastmod"])
    return (start + timedelta(days=364)).isoformat() + "T00:00:00Z"


def render_security(site: dict) -> str:
    base = site["url"].rstrip("/")
    return (
        f"Contact: {site['repo']}/security/advisories/new\n"
        f"Expires: {security_expires(site)}\n"
        "Preferred-Languages: ro, en\n"
        f"Canonical: {base}/.well-known/security.txt\n"
    )


def render_sitemap(site: dict, entries: list[dict]) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for entry in entries:
        parts.append("  <url>")
        parts.append(f"    <loc>{entry['loc']}</loc>")
        parts.append(f"    <lastmod>{entry['lastmod']}</lastmod>")
        parts.append(f"    <priority>{entry['priority']}</priority>")
        for alt in entry["hreflangs"]:
            parts.append(f'    <xhtml:link rel="alternate" hreflang="{alt["lang"]}" href="{alt["href"]}"/>')
        parts.append("  </url>")
    parts.append("</urlset>")
    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------- gates

SECRET_PATTERNS = [
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("stripe-key", re.compile(r"sk_(live|test)_[A-Za-z0-9]{8,}")),
    ("service-role", re.compile(r"service_role\s*[:=]\s*[A-Za-z0-9._-]{20,}")),
    ("postgres-url", re.compile(r"postgres(ql)?://[^\s\"'<]+")),
    ("mysql-url", re.compile(r"mysql://[^\s\"'<]+")),
    ("secret-assignment", re.compile(r"(?i)(password|passwd|pwd|secret|api[_-]?key|token)\s*[:=]\s*[^\s<]{6,}")),
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("private-ip", re.compile(r"\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")),
    ("supabase-host", re.compile(r"\b[a-z]{20}\.supabase\.co\b")),
    ("owner-path", re.compile(r"C:\\Users\\|/home/|/Users/")),
]

PLACEHOLDER_PATTERNS = [
    ("TODO", re.compile(r"\bTODO\b", re.I)),
    ("TBD", re.compile(r"\bTBD\b", re.I)),
    ("lorem", re.compile(r"\blorem\b", re.I)),
    ("YOUR_", re.compile(r"YOUR_")),
    ("placeholder", re.compile(r"\bplaceholder\b", re.I)),
    ("XXX", re.compile(r"\bXXX\b", re.I)),
    ("example.com", re.compile(r"example\.com", re.I)),
    ("coming soon", re.compile(r"coming soon", re.I)),
    ("[insert", re.compile(r"\[insert", re.I)),
    ("FIXME", re.compile(r"\bFIXME\b", re.I)),
]

EXTERNAL_PATTERNS = [
    ("external script", re.compile(r"<script[^>]+src=\"https?://", re.I)),
    ("external stylesheet", re.compile(r"<link[^>]+rel=\"stylesheet\"[^>]+href=\"https?://", re.I)),
    ("css import", re.compile(r"@import", re.I)),
    ("css url", re.compile(r"url\(\s*['\"]?https?://", re.I)),
    ("iframe", re.compile(r"<iframe\b", re.I)),
]

TEXT_SUFFIXES = {".html", ".css", ".js", ".json", ".svg", ".xml", ".txt", ".md"}


def gate_secrets(files: dict[str, bytes], source_files: list[Path]) -> None:
    hits = []
    for rel, data in sorted(files.items()):
        if Path(rel).suffix not in TEXT_SUFFIXES:
            continue
        text = data.decode("utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            for name, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    hits.append(f"docs/{rel}:{number}: {name}")
    for path in source_files:
        if path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            for name, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    hits.append(f"{path.relative_to(ROOT)}:{number}: {name}")
    if hits:
        die("secret scan failed:\n  " + "\n  ".join(hits))


def gate_placeholders(files: dict[str, bytes], source_files: list[Path]) -> None:
    hits = []
    for rel, data in sorted(files.items()):
        if Path(rel).suffix not in TEXT_SUFFIXES:
            continue
        text = data.decode("utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            for name, pattern in PLACEHOLDER_PATTERNS:
                if pattern.search(line):
                    hits.append(f"docs/{rel}:{number}: {name}")
    for path in source_files:
        if path.suffix not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            for name, pattern in PLACEHOLDER_PATTERNS:
                if pattern.search(line):
                    hits.append(f"{path.relative_to(ROOT)}:{number}: {name}")
    if hits:
        die("placeholder scan failed:\n  " + "\n  ".join(hits))


def gate_external(files: dict[str, bytes]) -> None:
    hits = []
    for rel, data in sorted(files.items()):
        if Path(rel).suffix not in {".html", ".css"}:
            continue
        text = data.decode("utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), 1):
            for name, pattern in EXTERNAL_PATTERNS:
                if pattern.search(line):
                    hits.append(f"docs/{rel}:{number}: {name}")
    if hits:
        die("external-request scan failed:\n  " + "\n  ".join(hits))


def gate_links(files: dict[str, bytes]) -> None:
    ids: dict[str, set[str]] = {}
    for rel, data in files.items():
        if rel.endswith(".html"):
            text = data.decode("utf-8")
            ids[rel] = set(re.findall(r'\bid="([^"]+)"', text))
    problems = []
    for rel, data in sorted(files.items()):
        if not rel.endswith(".html"):
            continue
        text = data.decode("utf-8")
        for match in re.finditer(r'(?:href|src)="([^"]+)"', text):
            target = html.unescape(match.group(1))
            if target.startswith(("http://", "https://", "mailto:", "#", "data:")):
                if target.startswith("#"):
                    if target[1:] and target[1:] not in ids.get(rel, set()):
                        problems.append(f"docs/{rel}: fragment {target} not found")
                continue
            if target.startswith("/"):
                path_part, _, fragment = target.partition("#")
                candidate = path_part.lstrip("/")
                if candidate == "":
                    candidate = "index.html"
                elif candidate.endswith("/"):
                    candidate += "index.html"
                if candidate not in files:
                    problems.append(f"docs/{rel}: {target} has no file")
                elif fragment and fragment not in ids.get(candidate, set()):
                    problems.append(f"docs/{rel}: {target} fragment not found")
    if problems:
        die("link check failed:\n  " + "\n  ".join(problems))


def gate_metadata(files: dict[str, bytes], pages: list[dict]) -> None:
    titles: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    problems = []
    for rel, data in sorted(files.items()):
        if not rel.endswith(".html"):
            continue
        text = data.decode("utf-8")
        if text.count("<h1") != 1:
            problems.append(f"docs/{rel}: {text.count('<h1')} h1 elements")
        title = re.search(r"<title>(.*?)</title>", text, re.S)
        desc = re.search(r'<meta name="description" content="([^"]*)"', text)
        if not title:
            problems.append(f"docs/{rel}: no title")
        else:
            value = html.unescape(title.group(1))
            if len(value) > 60:
                problems.append(f"docs/{rel}: title is {len(value)} characters")
            if rel != "404.html":
                if value in titles:
                    problems.append(f"docs/{rel}: duplicate title with {titles[value]}")
                titles[value] = rel
        if not desc:
            problems.append(f"docs/{rel}: no description")
        else:
            value = html.unescape(desc.group(1))
            if not 120 <= len(value) <= 160:
                problems.append(f"docs/{rel}: description is {len(value)} characters")
            if rel != "404.html":
                if value in descriptions:
                    problems.append(f"docs/{rel}: duplicate description with {descriptions[value]}")
                descriptions[value] = rel
        if rel != "404.html":
            if 'rel="canonical"' not in text:
                problems.append(f"docs/{rel}: no canonical")
            for lang in ("ro", "en", "x-default"):
                if f'hreflang="{lang}"' not in text:
                    problems.append(f"docs/{rel}: no hreflang {lang}")
    if problems:
        die("page metadata gate failed:\n  " + "\n  ".join(problems))


def keyword_sets(seo: dict) -> dict[str, list[str]]:
    """Every keyword set in seo.json, keyed by a readable label."""
    sets = {}
    for lang in LANGS:
        sets[f"site/{lang}"] = seo["site"][lang]["keywords"]
        sets[f"not_found/{lang}"] = seo["not_found"][lang]["keywords"]
    for name, block in seo["pages"].items():
        for lang in LANGS:
            sets[f"{name}/{lang}"] = block[lang]["keywords"]
    return sets


def gate_keywords(files: dict[str, bytes], seo: dict, pages: list[dict]) -> None:
    """Every page carries a keyword set for its language, and no set is reused
    on more than three pages."""
    problems = []
    for label, keywords in keyword_sets(seo).items():
        if len(keywords) < 8:
            problems.append(f"seo.json {label}: {len(keywords)} keywords, need 8 or more")
        if len(set(keywords)) != len(keywords):
            problems.append(f"seo.json {label}: duplicate keyword")
    counts: dict[str, list[str]] = {}
    for label, keywords in keyword_sets(seo).items():
        for keyword in keywords:
            counts.setdefault(keyword, []).append(label)
    for keyword, labels in sorted(counts.items()):
        if len(labels) > 3:
            problems.append(f"keyword {keyword!r} is on {len(labels)} pages: {', '.join(labels)}")

    for page in pages:
        for lang in LANGS:
            path = page["path"].get(lang)
            if not path:
                continue
            rel = path.lstrip("/")
            if rel == "":
                rel = "index.html"
            elif rel.endswith("/"):
                rel += "index.html"
            text = files.get(rel, b"").decode("utf-8")
            match = re.search(r'<meta name="keywords" content="([^"]*)"', text)
            if not match:
                problems.append(f"docs/{rel}: no keywords")
                continue
            emitted = [item.strip() for item in html.unescape(match.group(1)).split(",")]
            expected = seo_for(seo, page, lang)["keywords"]
            if emitted != expected:
                problems.append(f"docs/{rel}: keywords do not match seo.json")
            if len(emitted) < 8:
                problems.append(f"docs/{rel}: {len(emitted)} keywords, need 8 or more")
    if problems:
        die("keyword gate failed:\n  " + "\n  ".join(problems))


def gate_lengths(seo: dict) -> None:
    """Title at most 60 characters, description 120-160, in the data itself."""
    problems = []
    blocks = [("site", lang, seo["site"][lang]) for lang in LANGS]
    blocks += [("not_found", lang, seo["not_found"][lang]) for lang in LANGS]
    for name, block in seo["pages"].items():
        blocks += [(name, lang, block[lang]) for lang in LANGS]
    for name, lang, block in blocks:
        if len(block["title"]) > 60:
            problems.append(f"seo.json {name}/{lang}: title is {len(block['title'])} characters")
        if not 120 <= len(block["description"]) <= 160:
            problems.append(f"seo.json {name}/{lang}: description is {len(block['description'])} characters")
    if problems:
        die("SEO length gate failed:\n  " + "\n  ".join(problems))


def gate_hreflang(files: dict[str, bytes], site: dict, pages: list[dict]) -> None:
    """All three hreflang links on every page, pointing at the right counterpart."""
    problems = []
    for page in pages:
        if page["id"] == "404":
            continue
        ro_url = page_url(site, page["path"]["ro"])
        en_url = page_url(site, page["path"]["en"])
        expected = {"ro": ro_url, "en": en_url, "x-default": ro_url}
        for lang in LANGS:
            rel = page["path"][lang].lstrip("/")
            if rel == "":
                rel = "index.html"
            elif rel.endswith("/"):
                rel += "index.html"
            text = files.get(rel, b"").decode("utf-8")
            found = dict(
                (m.group(1), html.unescape(m.group(2)))
                for m in re.finditer(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', text)
            )
            for code, href in expected.items():
                if code not in found:
                    problems.append(f"docs/{rel}: no hreflang {code}")
                elif found[code] != href:
                    problems.append(f"docs/{rel}: hreflang {code} is {found[code]}, expected {href}")
            extra = sorted(set(found) - set(expected))
            if extra:
                problems.append(f"docs/{rel}: unexpected hreflang {', '.join(extra)}")
    if problems:
        die("hreflang gate failed:\n  " + "\n  ".join(problems))


def gate_structured(files: dict[str, bytes], pages: list[dict]) -> None:
    """The required JSON-LD types and their inLanguage on every page."""
    problems = []
    for page in pages:
        if page["id"] == "404":
            continue
        for lang in LANGS:
            rel = page["path"][lang].lstrip("/")
            if rel == "":
                rel = "index.html"
            elif rel.endswith("/"):
                rel += "index.html"
            text = files.get(rel, b"").decode("utf-8")
            blocks = []
            for raw in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
                try:
                    blocks.extend(json.loads(raw))
                except json.JSONDecodeError:
                    problems.append(f"docs/{rel}: JSON-LD does not parse")
                    blocks = []
                    break
            types = {block.get("@type"): block for block in blocks}
            required = ["WebPage"]
            if page["id"] == "home":
                required += ["WebSite", "SoftwareApplication"]
            if page["id"] in TECH_ARTICLE_PAGES:
                required.append("TechArticle")
            if page["id"] == "faq":
                required.append("FAQPage")
            for wanted in required:
                if wanted not in types:
                    problems.append(f"docs/{rel}: no {wanted}")
                elif types[wanted].get("inLanguage") != HTML_LANG[lang]:
                    problems.append(
                        f"docs/{rel}: {wanted} inLanguage is {types[wanted].get('inLanguage')!r}, expected {HTML_LANG[lang]!r}"
                    )
            if page["id"] == "faq" and "FAQPage" in types:
                visible = re.findall(r'<div class="faq-item"><h3>(.*?)</h3>', text, re.S)
                visible = [html.unescape(re.sub(r"<[^>]+>", "", item)).strip() for item in visible]
                structured = [item["name"] for item in types["FAQPage"]["mainEntity"]]
                if visible != structured:
                    problems.append(f"docs/{rel}: FAQPage questions do not mirror the visible ones")
    if problems:
        die("structured-data gate failed:\n  " + "\n  ".join(problems))


def gate_machine_files(files: dict[str, bytes], site: dict, pages: list[dict]) -> None:
    """llms.txt and security.txt exist, name the real host, and keep the RFC shape."""
    problems = []
    host = site["url"].rstrip("/")
    llms = files.get("llms.txt")
    if not llms:
        problems.append("no llms.txt")
    else:
        text = llms.decode("utf-8")
        if not text.startswith("# "):
            problems.append("llms.txt does not start with a title")
        if "\n> " not in text:
            problems.append("llms.txt has no summary line")
        links = re.findall(r"^- \[([^\]]+)\]\(([^)]+)\): (.+)$", text, re.M)
        if len(links) < 14:
            problems.append(f"llms.txt has {len(links)} links, expected at least 14")
        for _, href, summary in links:
            if not summary.strip():
                problems.append(f"llms.txt: link {href} has no description")
        # Page links must be absolute on the real host; the Optional section may
        # point at the repository and the sitemap.
        optional = text.split("## Optional", 1)[1] if "## Optional" in text else ""
        for _, href, _ in links:
            if href in optional:
                continue
            if not href.startswith(host + "/"):
                problems.append(f"llms.txt: link {href} is not on {host}")
        linked = {href for _, href, _ in links}
        for lang in LANGS:
            for page_id in ("install", "commands", "tools", "guides", "faq", "license"):
                page = next(p for p in pages if p["id"] == page_id)
                wanted = page_url(site, page["path"][lang])
                if wanted not in linked:
                    problems.append(f"llms.txt: no {lang} link to {wanted}")
    for rel in ("security.txt", ".well-known/security.txt"):
        data = files.get(rel)
        if not data:
            problems.append(f"no {rel}")
            continue
        text = data.decode("utf-8")
        fields = {}
        for line in text.splitlines():
            if ": " in line:
                key, value = line.split(": ", 1)
                fields[key] = value
        for key in ("Contact", "Expires", "Preferred-Languages", "Canonical"):
            if key not in fields:
                problems.append(f"{rel}: no {key}")
        if fields.get("Contact") != f"{site['repo']}/security/advisories/new":
            problems.append(f"{rel}: Contact is {fields.get('Contact')!r}")
        if fields.get("Canonical") != f"{host}/.well-known/security.txt":
            problems.append(f"{rel}: Canonical is {fields.get('Canonical')!r}")
        expires = fields.get("Expires", "")
        match = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})T\d{2}:\d{2}:\d{2}Z", expires)
        if not match:
            problems.append(f"{rel}: Expires {expires!r} is not RFC 3339")
        else:
            from datetime import date, timedelta

            day = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if not day <= date.fromisoformat(site["lastmod"]) + timedelta(days=365):
                problems.append(f"{rel}: Expires is more than a year after lastmod")
            if day < date.fromisoformat(site["lastmod"]):
                problems.append(f"{rel}: Expires is before lastmod")
        if fields.get("Preferred-Languages") != "ro, en":
            problems.append(f"{rel}: Preferred-Languages is {fields.get('Preferred-Languages')!r}")
    if problems:
        die("machine-readable gate failed:\n  " + "\n  ".join(problems))


def gate_primary_terms(files: dict[str, bytes], seo: dict, pages: list[dict]) -> None:
    """Every page's visible text uses each of its primary terms at least once."""
    problems = []
    for page in pages:
        for lang in LANGS:
            path = page["path"].get(lang)
            if not path:
                continue
            rel = path.lstrip("/")
            if rel == "":
                rel = "index.html"
            elif rel.endswith("/"):
                rel += "index.html"
            text = files.get(rel, b"").decode("utf-8")
            main = re.search(r"<main\b.*?</main>", text, re.S)
            if not main:
                problems.append(f"docs/{rel}: no main")
                continue
            plain = re.sub(r"<[^>]+>", " ", main.group(0))
            plain = html.unescape(plain)
            normalised = " ".join(plain.lower().split())
            for term in seo_for(seo, page, lang)["primary"]:
                if " ".join(term.lower().split()) not in normalised:
                    problems.append(f"docs/{rel}: primary term {term!r} does not appear in the text")
    if problems:
        die("primary-term gate failed:\n  " + "\n  ".join(problems))


def gate_sitemap_shape(files: dict[str, bytes], site: dict, pages: list[dict]) -> None:
    """The sitemap holds every page in both languages, and nothing else."""
    text = files.get("sitemap.xml", b"").decode("utf-8")
    locs = re.findall(r"<loc>(.*?)</loc>", text)
    expected = []
    for page in pages:
        if page["id"] == "404":
            continue
        for lang in LANGS:
            expected.append(page_url(site, canonical_path(page["path"][lang])))
    problems = []
    if sorted(locs) != sorted(expected):
        problems.append(f"sitemap has {len(locs)} URLs, expected {len(expected)}")
        for loc in sorted(set(expected) - set(locs)):
            problems.append(f"missing from sitemap: {loc}")
        for loc in sorted(set(locs) - set(expected)):
            problems.append(f"unexpected in sitemap: {loc}")
    for name in ("llms.txt", "security.txt"):
        if any(loc.endswith("/" + name) for loc in locs):
            problems.append(f"sitemap lists {name}, which is not a page")
    if problems:
        die("sitemap shape gate failed:\n  " + "\n  ".join(problems))


def gate_alt(files: dict[str, bytes]) -> None:
    problems = []
    for rel, data in sorted(files.items()):
        if not rel.endswith(".html"):
            continue
        text = data.decode("utf-8")
        for match in re.finditer(r"<img\b[^>]*>", text):
            tag = match.group(0)
            alt = re.search(r'alt="([^"]*)"', tag)
            if not alt or not alt.group(1).strip():
                problems.append(f"docs/{rel}: image without alt")
    if problems:
        die("alt-text gate failed:\n  " + "\n  ".join(problems))


def gate_jsonld(files: dict[str, bytes]) -> None:
    problems = []
    for rel, data in sorted(files.items()):
        if not rel.endswith(".html"):
            continue
        text = data.decode("utf-8")
        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', text, re.S):
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                problems.append(f"docs/{rel}: JSON-LD does not parse ({exc})")
    if problems:
        die("JSON-LD gate failed:\n  " + "\n  ".join(problems))


def gate_sitemap(files: dict[str, bytes], site: dict) -> None:
    data = files.get("sitemap.xml")
    if not data:
        die("sitemap gate: no sitemap.xml")
    text = data.decode("utf-8")
    problems = []
    for loc in re.findall(r"<loc>(.*?)</loc>", text):
        path = loc[len(site["url"].rstrip("/")) :]
        candidate = path.lstrip("/")
        if candidate == "":
            candidate = "index.html"
        elif candidate.endswith("/"):
            candidate += "index.html"
        if candidate not in files:
            problems.append(f"{loc} has no file")
    if problems:
        die("sitemap gate failed:\n  " + "\n  ".join(problems))


def gate_og(files: dict[str, bytes]) -> None:
    data = files.get("og.png")
    if not data:
        die("og gate: no og.png")
    width, height = png_size(data)
    if (width, height) != (1200, 630):
        die(f"og gate: og.png is {width}x{height}, expected 1200x630")


def gate_tokens(tokens: dict, css: str) -> None:
    static_css = (STATIC / "style.css").read_text(encoding="utf-8")
    problems = []
    for number, line in enumerate(static_css.splitlines(), 1):
        if re.search(r"#[0-9a-fA-F]{3,8}\b", line) or re.search(r"\b(rgb|rgba|hsl|hsla)\(", line):
            problems.append(f"site-revamp/static/style.css:{number}: literal colour")
    defined = set(re.findall(r"--([a-z0-9-]+):", css))
    for name in sorted(set(re.findall(r"var\(--([a-z0-9-]+)\)", css))):
        if name not in defined:
            problems.append(f"style.css: var(--{name}) is not defined")
    if problems:
        die("token gate failed:\n  " + "\n  ".join(problems))


def gate_contrast(tokens: dict) -> None:
    pairs = [
        ("text", "bg", 4.5), ("text", "surface", 4.5), ("text", "surface-2", 4.5),
        ("text-muted", "bg", 4.5), ("text-muted", "surface", 4.5),
        ("accent", "bg", 4.5), ("accent", "surface", 4.5),
        ("accent-contrast", "accent-strong", 4.5),
        ("success", "bg", 4.5), ("warning", "bg", 4.5), ("error", "bg", 4.5),
        ("border", "bg", 3.0), ("border", "surface", 3.0), ("focus", "bg", 3.0),
        ("text", "code-bg", 4.5),
    ]
    problems = []
    for fg, bg, minimum in pairs:
        ratio = contrast_ratio(tokens["color"][fg], tokens["color"][bg])
        if ratio < minimum:
            problems.append(f"{fg} on {bg}: {ratio:.2f}:1, needs {minimum}:1")
    if problems:
        die("contrast gate failed:\n  " + "\n  ".join(problems))


def gate_words(files: dict[str, bytes], pages: list[dict], lang: str) -> dict[str, int]:
    counts = {}
    problems = []
    for page in pages:
        if page["id"] == "404":
            continue
        path = page["path"][lang]
        rel = path.lstrip("/") or "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        text = files[rel].decode("utf-8")
        main = re.search(r"<main\b.*?</main>", text, re.S)
        if not main:
            problems.append(f"docs/{rel}: no main")
            continue
        count = words_in_html(main.group(0))
        counts[rel] = count
        bounds = page.get("words")
        if bounds and page["id"] != "tools":
            low, high = bounds
            if not low <= count <= high:
                problems.append(f"docs/{rel}: {count} words, expected {low}-{high}")
    if problems:
        die(f"word-count gate ({lang}) failed:\n  " + "\n  ".join(problems))
    return counts


def gate_language(pages: list[dict], files: dict[str, bytes]) -> None:
    problems = []
    for page in pages:
        if page["id"] == "404":
            continue
        for lang in LANGS:
            if not page["path"].get(lang):
                problems.append(f"{page['id']}: no {lang} path")
        if not page["path"].get("ro") or not page["path"].get("en"):
            continue
        ro = page["path"]["ro"].lstrip("/") or "index.html"
        en = page["path"]["en"].lstrip("/") or "index.html"
        if ro.endswith("/"):
            ro += "index.html"
        if en.endswith("/"):
            en += "index.html"
        if ro not in files:
            problems.append(f"{page['id']}: missing {ro}")
        if en not in files:
            problems.append(f"{page['id']}: missing {en}")
    if "404.html" not in files:
        problems.append("missing 404.html")
    if problems:
        die("language gate failed:\n  " + "\n  ".join(problems))


def gate_counts(ctx: dict, files: dict[str, bytes], pages: list[dict]) -> None:
    problems = []
    tools_src = (PRODUCT / "mcp_server.py").read_text(encoding="utf-8")
    tool_decorators = len(re.findall(r"@mcp\.tool\b", tools_src))
    prompt_decorators = len(re.findall(r"@mcp\.prompt\b", tools_src))
    resource_decorators = len(re.findall(r"@mcp\.resource\b", tools_src))
    if len(ctx["tools"]) != tool_decorators:
        problems.append(f"tools: extracted {len(ctx['tools'])}, decorators {tool_decorators}")
    if len(ctx["prompts"]) != prompt_decorators:
        problems.append(f"prompts: extracted {len(ctx['prompts'])}, decorators {prompt_decorators}")
    if len(ctx["resources"]) != resource_decorators:
        problems.append(f"resources: extracted {len(ctx['resources'])}, decorators {resource_decorators}")
    cli_src = (PRODUCT / "cli.py").read_text(encoding="utf-8")
    build = next(
        node for node in ast.parse(cli_src).body if isinstance(node, ast.FunctionDef) and node.name == "build_parser"
    )
    direct = 0
    for node in build.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and _is_attr(node.value.func, "sub", "add_parser"):
            direct += 1
        elif (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "set_defaults"
            and isinstance(node.value.func.value, ast.Call)
            and _is_attr(node.value.func.value.func, "sub", "add_parser")
        ):
            direct += 1
    harnesses = len(ctx["harnesses"])
    if len(ctx["commands"]) != direct + harnesses:
        problems.append(f"commands: extracted {len(ctx['commands'])}, direct subparsers {direct} + harnesses {harnesses}")
    for lang in LANGS:
        page = next(p for p in pages if p["id"] == "tools")
        rel = page["path"][lang].lstrip("/") + "index.html"
        rendered = files[rel].decode("utf-8").count('<tr id="tool-')
        if rendered != len(ctx["tools"]):
            problems.append(f"{rel}: {rendered} tool rows, real {len(ctx['tools'])}")
        page = next(p for p in pages if p["id"] == "commands")
        rel = page["path"][lang].lstrip("/") + "index.html"
        rendered = files[rel].decode("utf-8").count('<tr id="cmd-')
        if rendered != len(ctx["commands"]):
            problems.append(f"{rel}: {rendered} command rows, real {len(ctx['commands'])}")
    if problems:
        die("reference-count gate failed:\n  " + "\n  ".join(problems))


def gate_diagrams(files: dict[str, bytes]) -> None:
    problems = []
    for rel, data in sorted(files.items()):
        if not rel.startswith("assets/diagrams/") or not rel.endswith(".svg"):
            continue
        text = data.decode("utf-8")
        if 'role="img"' not in text:
            problems.append(f"docs/{rel}: no role=img")
        if "<title" not in text:
            problems.append(f"docs/{rel}: no title")
        if "<desc" not in text:
            problems.append(f"docs/{rel}: no desc")
    if problems:
        die("diagram gate failed:\n  " + "\n  ".join(problems))


def gate_claims(pages: list[dict]) -> None:
    problems = []
    for page in pages:
        claims = page.get("claims")
        if not claims:
            problems.append(f"{page['id']}: no claims")
            continue
        for index, claim in enumerate(claims, 1):
            for key in ("text", "evidence", "status"):
                if not claim.get(key):
                    problems.append(f"{page['id']} claim {index}: missing {key}")
            if claim.get("status") not in ("verified", "removed"):
                problems.append(f"{page['id']} claim {index}: status {claim.get('status')!r}")
            evidence = claim.get("evidence", "")
            for path in re.findall(r"([\w./-]+\.(?:md|py|toml|json|yml|txt|ps1|sh|html|css|js))(?::(\d+))?", evidence):
                name, line = path
                target = ROOT / name
                if not target.exists():
                    problems.append(f"{page['id']} claim {index}: evidence path {name} does not exist")
                elif line:
                    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
                    if int(line) > len(lines) or not lines[int(line) - 1].strip():
                        problems.append(f"{page['id']} claim {index}: {name}:{line} is empty or out of range")
    if problems:
        die("claims gate failed:\n  " + "\n  ".join(problems))


def gate_legal(files: dict[str, bytes], site: dict, pages: list[dict]) -> None:
    problems = []
    for page in pages:
        if page["id"] == "404":
            continue
        for lang in LANGS:
            rel = page["path"][lang].lstrip("/") + "index.html"
            text = files[rel].decode("utf-8")
            for key in ("license", "nonaffiliation"):
                if site["legal"][lang][key] not in text:
                    problems.append(f"docs/{rel}: missing legal text {key}")
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8").strip()
    license_rel = "licenta/index.html"
    if notice not in files[license_rel].decode("utf-8"):
        problems.append("docs/licenta/index.html: NOTICE is not verbatim")
    if notice not in files["en/license/index.html"].decode("utf-8"):
        problems.append("docs/en/license/index.html: NOTICE is not verbatim")
    if problems:
        die("legal gate failed:\n  " + "\n  ".join(problems))


# --------------------------------------------------------------------------- commands

def source_files() -> list[Path]:
    files = []
    for path in sorted(SITE_SRC.rglob("*")):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            files.append(path)
    return files


def collect_context(site: dict) -> dict:
    version = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    if not version:
        die("pyproject.toml: no version")
    site["version"] = version.group(1)
    return {
        "tools": extract_tools(),
        "prompts": extract_prompts(),
        "resources": extract_resources(),
        "commands": extract_commands(),
        "harnesses": extract_harness_names(),
    }


def render(site: dict, pages: list[dict], ctx: dict) -> dict[str, bytes]:
    seo = load_seo()
    files = build(site, pages, ctx)
    gate_secrets(files, source_files())
    gate_placeholders(files, source_files())
    gate_external(files)
    gate_links(files)
    gate_metadata(files, pages)
    gate_lengths(seo)
    gate_keywords(files, seo, pages)
    gate_hreflang(files, site, pages)
    gate_structured(files, pages)
    gate_primary_terms(files, seo, pages)
    gate_machine_files(files, site, pages)
    gate_sitemap_shape(files, site, pages)
    gate_alt(files)
    gate_jsonld(files)
    gate_sitemap(files, site)
    gate_og(files)
    gate_tokens(load_json(SITE_SRC / "design-tokens.json"), files["assets/style.css"].decode("utf-8"))
    gate_contrast(load_json(SITE_SRC / "design-tokens.json"))
    gate_language(pages, files)
    gate_counts(ctx, files, pages)
    gate_diagrams(files)
    gate_claims(pages)
    gate_legal(files, site, pages)
    return files


def main() -> int:
    global SITE_SRC, CONTENT, TEMPLATES, STATIC
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Build the ase-moodle documentation site.")
    parser.add_argument("--check", action="store_true", help="compare docs/ with a fresh build")
    parser.add_argument("--report", action="store_true", help="print word counts and reference counts")
    parser.add_argument("--claims", action="store_true", help="print the claims ledger")
    parser.add_argument("--source", type=Path, default=SITE_SRC, help="site source directory")
    parser.add_argument("--output", type=Path, default=DOCS, help="output directory")
    args = parser.parse_args()

    if args.source != SITE_SRC:
        SITE_SRC = args.source.resolve()
        CONTENT = SITE_SRC / "content"
        TEMPLATES = SITE_SRC / "templates"
        STATIC = SITE_SRC / "static"

    site = load_site()
    ctx = collect_context(site)
    pages = load_pages()
    values = {
        "version": site["version"],
        "tools": str(len(ctx["tools"])),
        "prompts": str(len(ctx["prompts"])),
        "resources": str(len(ctx["resources"])),
        "commands": str(len(ctx["commands"])),
        "harnesses": str(len(ctx["harnesses"])),
    }
    pages = [substitute(page, values) for page in pages]
    files = render(site, pages, ctx)

    if args.claims:
        print_claims(site, pages)
        return 0

    if args.report:
        for lang in LANGS:
            counts = gate_words(files, pages, lang)
            for rel, count in counts.items():
                print(f"{rel}: {count} words")
        print(f"tools: {len(ctx['tools'])}; prompts: {len(ctx['prompts'])}; resources: {len(ctx['resources'])}")
        print(f"commands: {len(ctx['commands'])}; harnesses: {', '.join(ctx['harnesses'])}")
        print(f"version: {site['version']}")
        return 0

    if args.check:
        differing = []
        for rel in sorted(files):
            target = args.output / rel
            if not target.exists() or target.read_bytes() != files[rel]:
                differing.append(rel)
        if differing:
            print("check: docs/ differs from a fresh build:")
            for rel in differing:
                print(f"  {rel}")
            return 1
        print("check: docs/ is byte-identical to a fresh build")
        return 0

    for rel in sorted(files):
        target = args.output / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(files[rel])
    print(f"build: wrote {len(files)} files to {args.output}")
    return 0


def print_claims(site: dict, pages: list[dict]) -> None:
    print("# Claims ledger — ase-moodle-mcp")
    print()
    print(f"Site: {site['url']} — lastmod {site['lastmod']}. Version {site['version']}.")
    print("Quoted wording is the Romanian page; the English page carries the same fact as a translation.")
    print()
    print("| # | Page | Claim (exact wording) | Evidence | Status |")
    print("|---|---|---|---|---|")
    index = 0
    for page in pages:
        for claim in page["claims"]:
            index += 1
            text = claim["text"].replace("|", "\\|")
            evidence = claim["evidence"].replace("|", "\\|")
            print(f"| {index} | {page['path']['ro']} | {text} | {evidence} | {claim['status']} |")


if __name__ == "__main__":
    raise SystemExit(main())
