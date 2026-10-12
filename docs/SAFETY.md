# Siguranță și reguli de utilizare

Pachetul poate face acțiuni reale în contul Moodle al studentului. Acest document spune ce cere confirmare, ce e blocat și ce nu se face automat. Pentru noțiunile de bază despre secrete, vezi [SECURITATE-PE-INTELES.md](SECURITATE-PE-INTELES.md).

## Citirile

Toate citirile (cursuri, teme, forumuri, note, quizuri, notificări, termene, funcțiile disponibile) rulează fără confirmare. Nu schimbă nimic în Moodle, cu o excepție: unele citiri marchează conținutul ca vizualizat, așa cum face și browserul.

## Scrierile și confirmarea

Scrierile cer `confirm=true` în MCP sau `--yes` în CLI. Fără ele, pachetul oprește acțiunea și întoarce eroarea `needs_confirmation` (cod `2` în CLI). Nimic nu se trimite.

| Acțiune | Confirmare |
|---|---|
| trimitere de fișier sau text la temă (ciornă sau final) | da |
| răspuns pe forum, discuție nouă | da |
| marcare notificare ca citită | da |
| pornire quiz, salvare răspunsuri, trimitere quiz | da (trimiterea e ireversibilă) |
| `call` sau `moodle_call` pentru funcție care scrie | da |
| citire orice | nu |
| descărcare de materiale (local, pe disc) | nu |
| login (`moodle_login`, `login`) | nu, dar deschide browserul |

**Recomandare pentru agenți:** setează `confirm=true` doar după ce studentul a aprobat exact conținutul, în aceeași conversație. Aprobarea pentru o acțiune nu acoperă următoarea.

`ASE_MOODLE_AUTO_CONFIRM=1` dezactivează confirmarea pentru toate scrierile. Nu îl recomand. Dacă îl setezi, agentul poate trimite lucruri fără să te întrebe.

## Temele fără ciorne

Moodle are două moduri pentru teme:

- **cu ciorne** (`drafts_enabled=true`): salvarea păstrează fișierul ca ciornă. Doar trimiterea finală îl face vizibil ca răspuns.
- **fără ciorne** (`drafts_enabled=false`): salvarea **trimite** fișierul imediat, ca răspuns final.

Pachetul verifică `drafts_enabled` înainte de orice upload. Dacă tema nu are ciorne și nu e trimitere finală, refuză cu eroarea `DirectSubmissionBlocked` și nu face nicio scriere. Pentru a forța totuși, trebuie `allow_direct=true` (`--allow-direct`).

Testul din octombrie 2026 arată ce se întâmplă: o salvare de test pe o temă fără ciorne a fost trimisă; a fost ștearsă din interfața Moodle (butonul „Șterge răspunsul”), iar statusul a revenit la `new`. Jurnalul Moodle păstrează istoricul.

## Quizurile

Pachetul permite răspunsul la quizuri, pentru că studentul a cerut-o. Fluxul recomandat:

1. `quiz_start`: pornește o încercare. Contează în limita permisă de Moodle.
2. `quiz_questions`: citește întrebările și câmpurile de răspuns.
3. `quiz_answer` cu `finish=false`: salvează răspunsurile, fără să le trimită.
4. Aprobarea studentului.
5. `quiz_answer` cu `finish=true`: trimite. Nu se poate anula.

Serverul respinge numele de câmpuri care nu există în încercare, înainte să trimită ceva.

**Nota de integritate academică.** Verifică regulile cursului înainte să folosești quizurile. Multe cursuri interzic ajutorul automat sau externalizarea răspunsurilor. Răspunderea pentru conținutul trimis e a studentului.

## Materiale descărcate

Materialele de curs sunt date neverificate. Pachetul nu le execută. Un fișier `.exe` din materialele de curs (de exemplu un laborator) rămâne un fișier până îl deschizi tu. Verifică înainte.

## Token și secrete

- Tokenul e stocat în Credential Manager sau Secret Service, nu în fișiere de proiect.
- Parola Google nu e salvată niciodată de pachet.
- `.env` și `config.json` sunt în `.gitignore`. Verifică `git status` înainte de commit.
- `doctor` și `auth-status` nu afișează tokenul.
- Erorile nu includ tokenul. Dacă vezi un token într-un log, e o problemă de raportat.

## Instalarea în clienți

- `install` modifică configurarea globală sau de proiect a clienților. Schimbarea de scop curăță celălalt scop: pot dispărea instalări din alte foldere. Vezi [PLATFORMS.md](PLATFORMS.md).
- Codex cere să marchezi folderul de proiect ca încredere. Nu-l marca decât dacă ai încredere în cod.
- Instalatorul face copii `.bak` înainte să modifice `opencode.json`.

## Ce nu face pachetul

- Nu trimite date către servere terțe. Singurele conexiuni sunt către Moodle-ul configurat și către GitHub (doar la instalare, pentru marketplace).
- Nu citește mesajele private: mesageria e dezactivată pe site.
- Nu schimbă parola și nu modifică setările contului Moodle.
- Nu rulează automat quizuri sau teme. Totul pornește dintr-o comandă sau dintr-un apel explicit al agentului.
