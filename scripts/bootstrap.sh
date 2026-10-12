#!/usr/bin/env bash
# Instalare completa pe Linux (sau macOS):
#   1. instaleaza pachetul ase-moodle (editabil, din clona)
#   2. instaleaza browserul pentru login (Chromium, o singura data; sari peste cu SKIP_BROWSER=1)
#   3. te logheaza in Moodle (browser; o singura data cu Google)
#   4. configureaza pluginul in Claude Code, Codex, opencode si Antigravity
#   5. verifica starea
#
# Utilizare (din radacina clonei):
#   bash scripts/bootstrap.sh                      # toate CLI-urile, scop global
#   bash scripts/bootstrap.sh owner/repo           # alta sursa pentru marketplace
#   SKIP_LOGIN=1 bash scripts/bootstrap.sh         # fara login (il faci mai tarziu: ase-moodle login)
#   TARGETS="claude codex" SCOPE=project bash scripts/bootstrap.sh   # doar anumite CLI-uri, pe folderul curent

set -euo pipefail

SOURCE="${1:-FiredMosquito831/ase-moodle}"
TARGETS="${TARGETS:-all}"
SCOPE="${SCOPE:-global}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CALLER_DIR="$PWD"   # folderul de unde rulezi scriptul: folosit pentru --scope project

PY="${PYTHON:-python3}"

echo "==> Pachet ase-moodle"
(cd "$ROOT" && "$PY" -m pip install -e . --quiet)

if [[ "${SKIP_BROWSER:-0}" != "1" ]]; then
  echo "==> Browser pentru login (Chromium; poate dura cateva minute prima data)"
  "$PY" -m playwright install chromium || echo "   (nu s-a putut instala Chromium; foloseste: ase-moodle login --method manual)"
fi

if [[ "${SKIP_LOGIN:-0}" != "1" ]]; then
  echo "==> Login Moodle (se deschide browserul; logheaza-te cu Google daca ti se cere)"
  "$PY" -m ase_moodle.cli login
fi

echo "==> Instalare in CLI-uri: $TARGETS (scop: $SCOPE)"
# shellcheck disable=SC2086
"$PY" -m ase_moodle.cli install $TARGETS --source "$SOURCE" --scope "$SCOPE" --project-dir "$CALLER_DIR"

echo "==> Verificare"
"$PY" -m ase_moodle.cli doctor
