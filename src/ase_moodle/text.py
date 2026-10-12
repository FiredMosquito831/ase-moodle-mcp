"""Utilitare de text: curata HTML-ul Moodle si genereaza nume de fisiere sigure pentru Windows."""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any

_LINK = re.compile(r"<a\s[^>]*?href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
_DROP = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_BLOCK = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6]|tr|table|section|article|blockquote)\b[^>]*>", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_INVALID_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_SPACES = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")


def html_to_text(fragment: str | None) -> str:
    """HTML Moodle -> text simplu. Linkurile raman vizibile ca `text (url)`."""
    if not fragment:
        return ""
    text = _DROP.sub("", fragment)
    text = _LINK.sub(lambda m: f"{_TAG.sub('', m.group(2)).strip()} ({m.group(1)})", text)
    text = _BLOCK.sub("\n", text)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = _SPACES.sub(" ", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()


def clean_filename(name: str | None, limit: int = 120) -> str:
    """Nume sigur pentru Windows/Linux: fara caractere interzise, fara punct final, lungime limitata."""
    cleaned = _INVALID_FILENAME.sub("_", name or "").strip().rstrip(".")
    return (cleaned or "_")[:limit]


def fmt_ts(value: Any) -> str | None:
    """Timestamp Unix Moodle -> '12.10.2026 14:00' (ora locala). None daca lipseste."""
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return datetime.fromtimestamp(number).strftime("%d.%m.%Y %H:%M")
