#!/usr/bin/env node
'use strict';

// Ruleaza dupa "npm install": instaleaza pachetul Python ase-moodle prin pipx.
// Sursa, in ordine: git (daca exista), arhiva de pe GitHub descarcata cu curl,
// apoi URL-ul arhivei, pe care pip il descarca singur.
// Nu blocheaza niciodata npm install: iesirea e mereu 0. Daca ceva lipseste,
// scrie ce trebuie facut, iar dupa ce rezolvi, ruleaza: npm rebuild -g ase-moodle-mcp

const { spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { findPython, INSTALL, SPEC } = require('../lib/run');

const ARCHIVE_URL = 'https://github.com/FiredMosquito831/ase-moodle-mcp/archive/refs/heads/main.tar.gz';

const log = (message) => process.stderr.write(`[ase-moodle-mcp] ${message}\n`);

function finish(message, code = 0) {
  log(message);
  process.exit(code);
}

function available(cmd) {
  const result = spawnSync(cmd, ['--version'], { windowsHide: true });
  return !result.error && result.status === 0;
}

// Comanda pipx: binarul din PATH, daca exista.
function pipxCommand() {
  if (available('pipx')) return { cmd: 'pipx', args: [] };
  return null;
}

// De unde instalam pachetul: git, apoi curl, apoi URL-ul direct.
// ASE_MOODLE_NO_GIT=1 forteaza fallback-ul (folosit la test).
function sourceSpec() {
  if (process.env.ASE_MOODLE_NO_GIT !== '1' && available('git')) {
    return { spec: SPEC, how: 'git' };
  }
  log('git lipseste sau e dezactivat, descarc arhiva de pe GitHub');
  if (available('curl')) {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ase-moodle-'));
    const file = path.join(dir, 'ase-moodle-mcp.tar.gz');
    const got = spawnSync('curl', ['-fsSL', '-o', file, ARCHIVE_URL], { stdio: 'inherit', windowsHide: true });
    if (got.status === 0) return { spec: file, how: 'curl' };
    log('curl nu a reusit descarcarea, folosesc URL-ul direct');
  }
  return { spec: ARCHIVE_URL, how: 'url' };
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

  const source = sourceSpec();
  log(`instalez pachetul Python ase-moodle prin pipx, sursa: ${source.how} (poate dura cateva minute)`);
  const install = spawnSync(pipx.cmd, [...pipx.args, 'install', '--force', source.spec], {
    stdio: 'inherit',
    windowsHide: true,
  });
  if (install.status !== 0) {
    return finish(`pipx nu a reusit instalarea. Incearca manual: ${INSTALL}`);
  }
  return finish('gata. Deschide un terminal nou, apoi ruleaza: ase-moodle login && ase-moodle install');
}

main();
