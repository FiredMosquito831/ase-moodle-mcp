"""Adaptoarele de harness. Fiecare modul e independent; registrul le indexeaza dupa nume.

Adaugi un harness nou: un modul nou (vezi docs/DEVELOPMENT.md) si o intrare aici. Nimic altceva.
"""

from .antigravity import AntigravityHarness
from .base import Capabilities, Ctx, Harness, Step, UnsupportedScope
from .claude import ClaudeHarness
from .codex import CodexHarness
from .opencode import OpencodeHarness

REGISTRY: dict[str, Harness] = {
    harness.name: harness
    for harness in (ClaudeHarness(), CodexHarness(), OpencodeHarness(), AntigravityHarness())
}

__all__ = ["REGISTRY", "Capabilities", "Ctx", "Harness", "Step", "UnsupportedScope"]
