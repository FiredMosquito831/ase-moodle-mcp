# Configurare

Setările vin din patru locuri. Prima valoare găsită câștigă.

| Prioritate | Sursă | Exemplu |
|---|---|---|
| 1 | variabile de mediu | `ASE_MOODLE_TOKEN=...` în sesiunea curentă |
| 2 | fișierul `.env` | `ASE_MOODLE_TOKEN=...` în `.env` |
| 3 | Credential Manager / Secret Service | tokenul salvat de `ase-moodle login` |
| 4 | `~/.ase-moodle/config.json` | URL-ul și, doar ca rezervă, tokenul |

## Variabile de mediu

| Variabilă | Implicit | Rol |
|---|---|---|
| `ASE_MOODLE_TOKEN` | — | tokenul Moodle |
| `ASE_MOODLE_URL` | `https://online.ase.ro` | adresa Moodle (ex. pentru serverul fals din teste) |
| `ASE_MOODLE_DOWNLOADS` | `~/ASE-Moodle` | folderul implicit pentru `download` |
| `ASE_MOODLE_ENV_FILE` | — | calea altui fișier `.env` (ex. `.env.test`) |
| `ASE_MOODLE_AUTO_CONFIRM` | — | `1` dezactivează confirmarea pentru scrieri. Nu se recomandă |

Variabilele din `.env` se citesc doar dacă nu există deja în mediu.

## Fișierul `.env`

Caută în această ordine:

1. calea din `ASE_MOODLE_ENV_FILE`, dacă e setată;
2. `.env` în folderul curent;
3. `.env` în folderele-părinte, până la rădăcină.

Formatul: `CHEIE=valoare` pe câte un rând. Liniile care încep cu `#` sunt comentarii. Valorile pot fi între ghilimele simple sau duble. Liniile fără `=` sau fără cheie sunt ignorate.

```text
# .env (local, nu-l comite)
ASE_MOODLE_TOKEN=pune-tokenul-aici
ASE_MOODLE_DOWNLOADS=D:\Materiale
```

`.env.example` e fișierul de model, fără valori reale. `.env.test` e pentru serverul fals din teste (vezi [TESTING.md](TESTING.md)).

## `~/.ase-moodle/config.json`

Conține de obicei:

```json
{
  "base_url": "https://online.ase.ro",
  "token_store": "keyring",
  "username": "..."
}
```

- `token_store`: `keyring` (tokenul e în Credential Manager sau Secret Service) sau `file` (tokenul e în același fișier, cu permisiuni restrânse).
- Nu conține parola Google.
- Pe Windows și Linux, fișierul are acces doar pentru tine.

## Folderul de descărcare

`ase-moodle download` pune materialele în `ASE_MOODLE_DOWNLOADS`, sau în `~/ASE-Moodle` dacă variabila lipsește. `--out DIR` are prioritate față de ambele.

Structura: `<Materie> - <CURS|SEMINAR|LABORATOR>/<secțiune>/...`, cu `index.md`, `teme.md`, `forumuri/`, `quizuri.md`, `note.md`, `linkuri.txt` și `_raw/*.json`.

## Folderul proiectului (instalare pe scop de proiect)

Nu e o variabilă de mediu. Se dă la comandă: `--project-dir DIR`. Dacă lipsește, e folderul curent. Vezi [PLATFORMS.md](PLATFORMS.md).

## Adresa Moodle

Implicit: `https://online.ase.ro`. Se schimbă cu `ASE_MOODLE_URL` sau cu `--base-url` la `login`. Pachetul e scris pentru BL@ASE (Moodle 4.1). Alte instanțe Moodle ar putea funcționa, dar nu sunt testate.

## Verificare

```powershell
ase-moodle doctor
```

Arată sursa tokenului (`env`, `dotenv`, `keyring`, `file`) și dacă există un `.env`. Nu arată tokenul.
