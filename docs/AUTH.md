# Autentificare

Pachetul are nevoie de un **token Moodle** (un șir de 32 de caractere). Tokenul e legat de contul tău, nu de folder sau de calculator. Cine îl are poate face lucruri în contul tău, deci se tratează ca o parolă.

Login-ul pe online.ase.ro se face doar prin Google. Nu există login cu nume de utilizator și parolă pentru pachet.

## Cum obții tokenul

### Metoda browser (implicită)

```powershell
ase-moodle login
```

Pașii:

1. Se deschide Edge (sau Chrome, sau Chromium pe Linux) cu un profil dedicat, în `~/.ase-moodle/browser-profile`.
2. Prima dată, te loghezi cu Google în fereastra care se deschide.
3. Pachetul deschide `launch.php` (fluxul SSO al aplicației Moodle Mobile). Moodle redirecționează către `moodlemobile://token=...`, iar pachetul prinde URL-ul și extrage tokenul.
4. Tokenul e verificat cu un apel real și salvat.

Rulările următoare sunt automate, cât timp sesiunea Google e valabilă. Nu mai e nevoie de login.

Dacă Playwright nu e instalat, `auto` trece pe metoda `manual`.

### Metoda manual

```powershell
ase-moodle login --method manual
```

Se deschide pagina de login (cu redirect la „Chei de securitate”). Te loghezi, copiezi tokenul „Moodle mobile web service” din tabel, iar pachetul îl citește din clipboard și îl salvează.

### Token direct

```powershell
ase-moodle login --token TOKEN
echo TOKEN | ase-moodle login --token-stdin
```

Util pentru scripturi sau dacă ai deja tokenul. Tokenul apare în istoricul shell-ului în cazul `--token`. Preferă `--token-stdin` sau metoda browser.

### Obținerea tokenului fără pachet

Online.ase.ro → Preferințe → Chei de securitate → rândul „Moodle mobile web service” → copiezi valoarea. Dacă tokenul nu apare, metoda browser îl va crea prin fluxul SSO.

## Unde se salvează

| Ce | Windows | Linux |
|---|---|---|
| Tokenul | Windows Credential Manager (serviciul `ase-moodle`) | Secret Service (dacă e disponibil), altfel `~/.ase-moodle/config.json` cu `chmod 600` |
| URL-ul Moodle și eticheta sursei | `%USERPROFILE%\.ase-moodle\config.json` | `~/.ase-moodle/config.json` |
| Sesiunea Google (profilul browserului) | `%USERPROFILE%\.ase-moodle\browser-profile` (ACL doar pentru tine) | `~/.ase-moodle/browser-profile` (`chmod 700`) |

Tokenul nu se afișează niciodată. `auth-status` și `doctor` spun doar de unde a fost citit (`keyring`, `env`, `dotenv`, `file`).

**Migrare:** dacă aveai tokenul în clar în `config.json` (versiuni vechi), la prima citire e mutat automat în Credential Manager, iar fișierul rămâne fără token.

## Parola Google

Pachetul **nu salvează parola Google**, nici în Credential Manager, nici în `.env`, nici în fișiere. Te loghezi tu în browser. Sesiunea rămâne în profilul browserului, iar dacă expiră, fereastra se redeschide și te loghezi din nou.

Dacă ai scris parola într-un loc nesigur (chat, fișier, screenshot), schimb-o. Vezi [SECURITATE-PE-INTELES.md](SECURITATE-PE-INTELES.md).

## Verificare

```powershell
ase-moodle auth-status
```

Răspuns valid: `{"logged_in": true, "user": "...", "base_url": "https://online.ase.ro"}`.

## Deconectare și revocare

```powershell
ase-moodle logout                      # șterge tokenul din Credential Manager și config
ase-moodle logout --forget-browser     # și sesiunea Google din profilul browserului
```

Pentru a invalida tokenul complet, din Moodle: Chei de securitate → „Reseteaza” la rândul „Moodle mobile web service”. Tokenul vechi nu mai funcționează, iar pachetul trebuie să-l obțină din nou cu `ase-moodle login`.

Schimbarea parolei Google nu invalidează tokenul Moodle. Dacă bănuiești că tokenul a fost expus, resetează-l din Moodle.

## Ordinea de citire a tokenului

1. `ASE_MOODLE_TOKEN` din mediu.
2. `ASE_MOODLE_TOKEN` din fișierul `.env` (vezi [CONFIGURATION.md](CONFIGURATION.md)).
3. Credential Manager (sau Secret Service pe Linux).
4. Rezerva din `config.json` (doar dacă keyring nu e disponibil).

## Probleme

Vezi [TROUBLESHOOTING.md](TROUBLESHOOTING.md): login expirat, browser lipsă, clipboard gol, token invalid.
