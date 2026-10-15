#!/usr/bin/env node
'use strict';

// Ruleaza dupa "npm install": instaleaza pachetul Python ase-moodle prin pipx.
// Nu blocheaza niciodata npm install: iesirea e mereu 0. Daca ceva lipseste,
// scrie ce trebuie facut, iar dupa ce rezolvi, ruleaza: npm rebuild -g ase-moodle-mcp

const { spawnSync } = require('child_process');
const { findPython, INSTALL, SPEC } = require('../lib/run');

const log = (message) => process.stderr.write(`[ase-moodle-mcp] ${message}\n`);

function finish(message, code = 0) {
  log(message);
  process.exit(code);
}

// Comanda pipx: fie binarul din PATH, fie modulul din Python-ul gasit.
function pipxCommand() {
  const direct = spawnSync('pipx', ['--version'], { windowsHide: true });
  if (!direct.error && direct.status === 0) return { cmd: 'pipx', args: [] };
  return null;
}

function main() {
  const py = findPython();
  const forced = process.env.ASE_MOODLE_FORCE_INSTALL === '1';

  if (py && py.hasModule && !forced) {
    return finish('pachetul Python ase-moodle e deja instalat. Urmatorul pas: ase-moodle login');
  }
  if (!py) {
    return finish('nu gasesc Python 3.10+. Instaleaza-l de pe python.org, apoi ruleaza: npm rebuild -g ase-moodle-mcp');
  }

  let pipx = pipxCommand();
  if (!pipx) {
    log('pipx lipseste, il instalez cu pip --user');
    const pip = spawnSync(py.cmd, [...py.pre, '-m', 'pip', 'install', '--user', '--quiet', 'pipx'], {
      stdio: 'inherit',
      windowsHide: true,
    });
    if (pip.status !== 0) {
      return finish(`nu am putut instala pipx. Instaleaza-l manual, apoi ruleaza: ${INSTALL}`);
    }
    pipx = { cmd: py.cmd, args: [...py.pre, '-m', 'pipx'] };
    // Pune directorul binarelor pipx in PATH-ul utilizatorului (o singura data).
    spawnSync(pipx.cmd, [...pipx.args, 'ensurepath'], { stdio: 'inherit', windowsHide: true });
  }

  log('instalez pachetul Python ase-moodle prin pipx (poate dura cateva minute)');
  const install = spawnSync(pipx.cmd, [...pipx.args, 'install', '--force', SPEC], {
    stdio: 'inherit',
    windowsHide: true,
  });
  if (install.status !== 0) {
    return finish(`pipx nu a reusit instalarea. Incearca manual: ${INSTALL}`);
  }
  return finish('gata. Deschide un terminal nou, apoi ruleaza: ase-moodle login && ase-moodle install');
}

main();
