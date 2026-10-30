#!/usr/bin/env python3
"""Smoke test MCP prin stdio: porneste o comanda de server si verifica handshake-ul si lista de unelte.

Utilizare:
    python tests/smoke_mcp.py [--tools 28] [--timeout 180] -- <comanda...>
    python tests/smoke_mcp.py -- uvx --isolated --from dist/ase_moodle-0.2.4-py3-none-any.whl ase-moodle-mcp

Trimite `initialize` imediat (ca un client real), apoi `notifications/initialized` si `tools/list`.
Nu apeleaza nicio unealta. Serverul primeste ASE_MOODLE_URL=http://127.0.0.1:9 (nimic nu asculta acolo),
un fisier .env inexistent, keyring-ul nul si un home temporar, ca sa nu poata citi tokenul real.

Nu este un test unittest (numele nu incepe cu test_): `unittest discover` nu il colecteaza.
Exit: 0 = numarul de unelte e cel asteptat; 1 = alt numar sau eroare de protocol; 2 = timeout.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

PROTOCOL_VERSION = "2025-06-18"
DEAD_MOODLE = "http://127.0.0.1:9"


class SmokeError(RuntimeError):
    pass


class SmokeTimeout(SmokeError):
    pass


def server_env(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    for name in ("ASE_MOODLE_TOKEN", "ASE_MOODLE_DOWNLOADS"):
        env.pop(name, None)
    env.update({
        "ASE_MOODLE_URL": DEAD_MOODLE,
        "ASE_MOODLE_ENV_FILE": str(home / "nu-exista.env"),
        "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring",
        "HOME": str(home),
        "USERPROFILE": str(home),
        "PYTHONIOENCODING": "utf-8",
    })
    return env


def _reader(stream, lines: queue.Queue) -> None:
    for raw in iter(stream.readline, b""):
        lines.put(raw)
    lines.put(None)


def _send(proc: subprocess.Popen, message: dict) -> None:
    proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
    proc.stdin.flush()


def _wait_for(lines: queue.Queue, request_id: int, deadline: float) -> dict:
    """Raspunsul cu id-ul cerut; notificarile si liniile care nu sunt JSON se ignora."""
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            raise SmokeTimeout(f"niciun raspuns la cererea {request_id} in timpul limitei")
        try:
            raw = lines.get(timeout=left)
        except queue.Empty:
            continue
        if raw is None:
            raise SmokeError(f"serverul a inchis stdout inainte de raspunsul {request_id}")
        try:
            message = json.loads(raw)
        except ValueError:
            sys.stderr.write(f"[smoke] linie ignorata pe stdout: {raw[:200]!r}\n")
            continue
        if isinstance(message, dict) and message.get("id") == request_id:
            if "error" in message:
                raise SmokeError(f"eroare la cererea {request_id}: {message['error']}")
            return message["result"]


def _stop(proc: subprocess.Popen) -> int | None:
    """Inchide stdin (serverul iese singur la EOF); daca nu iese, opreste doar procesul pornit aici."""
    try:
        proc.stdin.close()
    except OSError:
        pass
    try:
        return proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        pass
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    else:
        proc.kill()
    try:
        return proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        return None


def smoke(command: list[str], timeout: float) -> dict:
    with tempfile.TemporaryDirectory(prefix="ase-moodle-smoke-") as tmp:
        home = Path(tmp)
        start = time.monotonic()
        deadline = start + timeout
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=server_env(home), cwd=tmp)
        lines: queue.Queue = queue.Queue()
        threading.Thread(target=_reader, args=(proc.stdout, lines), daemon=True).start()
        try:
            _send(proc, {
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "ase-moodle-smoke", "version": "1"},
                },
            })
            init = _wait_for(lines, 1, deadline)
            t_init = time.monotonic() - start
            _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            tools = _wait_for(lines, 2, deadline).get("tools", [])
            t_tools = time.monotonic() - start
        finally:
            code = _stop(proc)
        return {
            "server": init.get("serverInfo", {}),
            "protocol": init.get("protocolVersion"),
            "tools": sorted(t["name"] for t in tools),
            "initialize_s": round(t_init, 2),
            "tools_s": round(t_tools, 2),
            "exit_code": code,
        }


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in argv:
        print("utilizare: python tests/smoke_mcp.py [--tools N] [--timeout S] -- <comanda...>", file=sys.stderr)
        return 1
    split = argv.index("--")
    parser = argparse.ArgumentParser(description="Handshake MCP prin stdio + numarul de unelte.")
    parser.add_argument("--tools", type=int, default=28, help="numarul asteptat de unelte (implicit 28)")
    parser.add_argument("--timeout", type=float, default=180.0, help="secunde pentru tot handshake-ul (implicit 180)")
    args = parser.parse_args(argv[:split])
    command = argv[split + 1:]
    if not command:
        print("lipseste comanda dupa --", file=sys.stderr)
        return 1
    print(f"[smoke] comanda: {subprocess.list2cmdline(command)}", flush=True)
    try:
        result = smoke(command, args.timeout)
    except SmokeTimeout as exc:
        print(f"[smoke] TIMEOUT: {exc}", file=sys.stderr)
        return 2
    except (SmokeError, OSError) as exc:
        print(f"[smoke] EROARE: {exc}", file=sys.stderr)
        return 1
    count = len(result["tools"])
    print(f"[smoke] server={result['server'].get('name')} {result['server'].get('version')} "
          f"protocol={result['protocol']} initialize={result['initialize_s']}s "
          f"tools/list={result['tools_s']}s tools={count} exit={result['exit_code']}", flush=True)
    if count != args.tools:
        print(f"[smoke] astept {args.tools} unelte, am primit {count}: {result['tools']}", file=sys.stderr)
        return 1
    print("[smoke] OK", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
