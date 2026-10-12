# ase-moodle: BL@ASE (online.ase.ro) pentru agenți AI

Client Python, CLI, server MCP și plugin pentru Moodle-ul BL@ASE. Îți permite să folosești contul tău de Moodle din Claude Code, Codex, opencode și Google Antigravity: cursuri, materiale, teme, forumuri, note, quizuri, notificări și termene.

Repo-ul este **privat**. Conține logica de acces la contul tău.

## Ce poate face

- listează cursurile pe an de studiu, semestru și tip (CURS / SEMINAR / LABORATOR);
- descarcă materialele unui curs sau ale unui an, în paralel: fișiere, pagini, linkuri, teme, forumuri, quizuri, note;
- citește temele, starea trimiterii și feedbackul; vede dacă o temă are ciorne;
- trimite teme (ciornă sau final), răspunde pe forum, deschide discuții (cu confirmarea ta);
- răspunde la quizuri: citește întrebările, salvează răspunsurile, trimite încercarea (cu aprobarea ta);
- vede notificările și termenele, marchează notificările ca citite;
- apelează orice funcție Web Service Moodle (395 disponibile pentru token).

## Pornire rapidă

**Windows:**

```powershell
git clone https://github.com/FiredMosquito831/ase-moodle.git
cd ase-moodle
powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1
```

**Linux (și macOS):**

```bash
git clone https://github.com/FiredMosquito831/ase-moodle.git
cd ase-moodle
bash scripts/bootstrap.sh
```

Scriptul instalează pachetul, te loghează (se deschide browserul; o singură dată, cu Google), configurează Claude Code, Codex, opencode și Antigravity și verifică starea.

Pași manuali și variante (scop de proiect, instalare din GitHub, Linux) sunt în [docs/INSTALL.md](docs/INSTALL.md).

## Comenzi de bază

```powershell
ase-moodle login                              # token (browser; sau --method manual)
ase-moodle auth-status                        # ești logat?
ase-moodle install                            # configurează toate CLI-urile (global)
ase-moodle install claude --scope project     # doar folderul curent
ase-moodle codex doctor                       # un singur harness: install|update|uninstall|doctor
ase-moodle doctor                             # starea instalării
ase-moodle deadlines --days 14
ase-moodle download --year 3 --sem 1 --out D:\Materiale
```

Lista completă: [docs/USAGE.md](docs/USAGE.md).

## Documentație

| Document | Ce conține |
|---|---|
| [docs/INSTALL.md](docs/INSTALL.md) | cerințe pe Windows și Linux, cele trei variante de instalare, actualizare, dezinstalare |
| [docs/USAGE.md](docs/USAGE.md) | referința CLI: fiecare comandă, opțiune, exemplu, coduri de ieșire |
| [docs/MCP.md](docs/MCP.md) | cele 28 de unelte MCP, prompturile, resursele, conectarea clienților |
| [docs/PLATFORMS.md](docs/PLATFORMS.md) | Claude Code, Codex, opencode, Antigravity: ce se instalează, scopurile, fișierele atinse |
| [docs/HARNESSES.md](docs/HARNESSES.md) | adaptoarele izolate: comenzile per harness, evidența fiecăruia, ce returnează `doctor` |
| [docs/AUTH.md](docs/AUTH.md) | obținerea tokenului, unde e stocat, parola Google, deconectare |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | variabile de mediu, `.env`, `config.json`, folderul de descărcare |
| [docs/SAFETY.md](docs/SAFETY.md) | confirmări, garda pentru ciorne, politica pentru quizuri, reguli de utilizare |
| [docs/SECURITATE-PE-INTELES.md](docs/SECURITATE-PE-INTELES.md) | noțiuni de bază despre secrete, explicate simplu |
| [docs/TESTING.md](docs/TESTING.md) | suita de teste, serverul Moodle fals, CI, ce e și ce nu e testat |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | structura codului, cum adaugi o funcție, versiuni, lansare |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | erori frecvente și cum le rezolvi |

## Stare verificată

Verificat pe contul real (2026-10-12):

- autentificare prin browser (SSO) și salvare în Credential Manager;
- cursuri, teme, forumuri, notificări, termene, note, quizuri (citire);
- descărcarea anului 3, semestrul 1: 33 de fișiere, fără erori; a doua rulare nu descarcă nimic;
- erori fără efecte: quiz închis, obiecte inexistente, fișier inexistent;
- garda pentru ciorne: refuză o salvare pe o temă fără ciorne, fără să trimită nimic;
- instalare, update, dezinstalare și reinstalare pe cele patru platforme; `doctor` OK;
- testele trec pe Windows și pe Linux (WSL Ubuntu 24.04).

Netestat pe contul real: un quiz deschis completat de la cap la coadă și o trimitere reală cu ciorne activate (nu există astfel de situații acum). Detalii în [docs/TESTING.md](docs/TESTING.md).

## Limite

- Mesageria Moodle este dezactivată pe site.
- Funcțiile Web Service sunt cele ale serviciului mobil Moodle. Ce există doar în interfața web nu se acoperă.
- Antigravity se instalează doar global.
- macOS nu e testat.
