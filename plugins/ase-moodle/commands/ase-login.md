---
description: Verifica conexiunea la Moodle BL@ASE si, daca lipseste, te logheaza (browser cu Google)
---

Verifica mai intai cu `auth_status` din serverul MCP `ase-moodle`.

- Daca `logged_in` este adevarat: spune cui apartine contul si ca totul e in regula.
- Daca nu: apeleaza `moodle_login` (method `auto`). Se deschide un browser; studentul se logheaza cu Google
  (doar prima data). Spune-i ca trebuie sa faca login in fereastra care se deschide.
- Nu afisa niciodata tokenul, nici parti din el.
