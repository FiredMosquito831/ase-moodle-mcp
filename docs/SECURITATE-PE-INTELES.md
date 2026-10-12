# Securitate, pe intelesul tuturor

Ideea de baza: unele lucruri sunt **secrete** (cine le are poate face lucruri in contul tau), altele sunt **publice**
(nu te pot afecta). Regula simpla: **secretele nu ies niciodata din calculatorul tau si nu intra niciodata in git.**

## Ce este secret, ce nu

| Lucru | Secret? | Unde ramane |
|---|---|---|
| Tokenul Moodle (sirul de 32 de caractere din Chei de securitate) | **DA** | Windows Credential Manager (sau `.env` local) |
| Parola contului Google | **DA** | Nu o salvam nicaieri. O introduci tu in browser |
| Sesiunea de browser din `~/.ase-moodle/browser-profile` | **DA** (e ca o cheie) | Local; `ase-moodle logout --forget-browser` o sterge |
| Fisierul `.env` cu valori reale | **DA** | Local; e in `.gitignore` |
| Materialele descarcate (cursuri, teme) | Nu, dar sunt ale facultatii | `~/ASE-Moodle`, nu in repo |
| Codul proiectului, numele cursurilor, structura | Nu | Poate fi in git |
| `.env.example` si `.env.test` | Nu (nu au valori reale) | Pot fi in git |

## Cum functioneaza in proiectul asta

1. **Tokenul** se salveaza in Credential Manager-ul Windows: un "seif" al sistemului de operare, protejat de contul tau.
   Fisierul `config.json` contine doar adresa Moodle si o eticheta, nu tokenul.
2. **Parola Google** nu se salveaza. Te loghezi tu, o data, in fereastra care se deschide. Apoi sesiunea ramane in
   profilul browserului, iar tokenul se ia automat. Daca sesiunea expira, fereastra se redeschide si te loghezi din nou.
3. **`.env`** este un fisier local cu variabile (de exemplu `ASE_MOODLE_TOKEN=...`). Este util pentru teste, dar e mai
   putin sigur decat Credential Manager-ul. Daca il folosesti, tine-l doar local.
4. **Testele** ruleaza pe un server Moodle **fals** (`tests/fake_moodle.py`), cu nume inventate. Nu ating contul tau
   si nu folosesc internetul. Asa poti testa fara risc.

## Regulile de aur

- Nu pune tokenul sau parola in chat, in fisiere din proiect, in commit-uri sau in mesaje de eroare.
  Daca le-ai scris cumva intr-un loc unde nu trebuia: **schimba-le** (Chei de securitate -> Reseteaza; parola Google
  din setarile contului).
- Inainte de `git commit`, ruleaza `git status`: nu trebuie sa apara `.env` sau `config.json`.
- Un repo **privat** e mai sigur decat unul public, chiar daca nu contine secrete. Tine-l privat.
- Daca un secret a iesit (chat, screenshot, commit): **il consideri compromis** si il inlocuiesti. Stergerea din
  fisier nu ajunge, pentru ca ramane in istoric.
- Scrierile in Moodle (trimiteri, raspunsuri la quiz, mesaje) cer confirmare. Nu le dezactiva decat daca stii exact ce faci.

## Ce ai de facut acum

- Parola Google care a aparut in chat: **schimb-o** din setarile contului Google, ca precautie.
- Tokenul a aparut in rezultatele unor comenzi. Daca vrei zero risc: Chei de securitate -> Reseteaza, apoi
  `ase-moodle login`.
