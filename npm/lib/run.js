'use strict';
// Launcher pentru pachetul Python ase-moodle. Nu contine logica aplicatiei:
// gaseste un Python 3.10+ cu pachetul instalat si ii paseaza argumentele.
// Mesajele merg pe stderr: pe stdout vorbeste serverul MCP.

const { spawn, spawnSync } = require('child_process');

const SPEC = 'git+https://github.com/FiredMosquito831/ase-moodle-mcp.git';
const INSTALL = `pipx install ${SPEC}`;
const PROBE = "import sys,importlib.util as u;print(int(sys.version_info>=(3,10)),int(u.find_spec('ase_moodle') is not None))";

// Scripturile Python apelate pentru fiecare comanda.
const SCRIPTS = {
  cli: 'import sys; from ase_moodle.cli import main; raise SystemExit(main(sys.argv[1:]))',
  mcp: 'from ase_moodle.mcp_server import main; main()',
};

function fail(message) {
  process.stderr.write(message + '\n');
  process.exit(1);
}

function candidates() {
  if (process.platform === 'win32') {
    return [['py', ['-3']], ['python', []], ['python3', []]];
  }
  return [['python3', []], ['python', []]];
}

// Intoarce primul Python 3.10+ gasit, preferand unul care are pachetul ase-moodle.
function findPython() {
  let fallback = null;
  for (const [cmd, pre] of candidates()) {
    const result = spawnSync(cmd, [...pre, '-c', PROBE], { encoding: 'utf8', windowsHide: true });
    if (result.error || result.status !== 0) continue;
    const [versionOk, hasModule] = result.stdout.trim().split(/\s+/).map((v) => v === '1');
    if (!versionOk) continue;
    const entry = { cmd, pre, hasModule };
    if (hasModule) return entry;
    fallback = fallback || entry;
  }
  return fallback;
}

function launch(kind, args) {
  const py = findPython();
  if (!py) {
    fail('Nu gasesc Python 3.10 sau mai nou in PATH. Instaleaza-l de pe python.org.');
  }
  if (!py.hasModule) {
    fail(`Pachetul ase-moodle nu e instalat pentru ${py.cmd}.\nRuleaza:\n  ${INSTALL}`);
  }
  const child = spawn(py.cmd, [...py.pre, '-c', SCRIPTS[kind], ...args], {
    stdio: 'inherit',
    windowsHide: true,
  });
  for (const signal of ['SIGINT', 'SIGTERM']) {
    process.on(signal, () => child.kill(signal));
  }
  child.on('error', (error) => fail(error.message));
  child.on('exit', (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
}

module.exports = { launch, findPython, INSTALL, SPEC };
