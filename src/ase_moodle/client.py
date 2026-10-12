"""Client minimal pentru Moodle Web Services (REST) de pe online.ase.ro."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

import httpx

REST_PATH = "/webservice/rest/server.php"
UPLOAD_PATH = "/webservice/upload.php"


class MoodleError(RuntimeError):
    """Eroare returnata de Moodle sau de retea, cu codul Moodle daca exista."""

    def __init__(self, message: str, errorcode: str | None = None, function: str | None = None):
        super().__init__(message)
        self.errorcode = errorcode
        self.function = function


def flatten_params(params: dict[str, Any] | None) -> dict[str, str]:
    """Transforma dict/list in forma Moodle: courseids[0]=1, plugindata[onlinetext_editor][text]=..."""
    flat: dict[str, str] = {}

    def walk(key: str, value: Any) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                walk(f"{key}[{sub_key}]", sub_value)
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                walk(f"{key}[{index}]", item)
        elif isinstance(value, bool):
            flat[key] = "1" if value else "0"
        else:
            flat[key] = str(value)

    for name, value in (params or {}).items():
        walk(name, value)
    return flat


class MoodleClient:
    def __init__(self, base_url: str, token: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._http = httpx.Client(timeout=timeout, follow_redirects=True)
        self._siteinfo: dict[str, Any] | None = None

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "MoodleClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def call(self, wsfunction: str, params: dict[str, Any] | None = None) -> Any:
        """Apeleaza orice functie Web Service Moodle. Ridica MoodleError daca Moodle raporteaza eroare."""
        data = {"wstoken": self.token, "wsfunction": wsfunction, "moodlewsrestformat": "json"}
        data.update(flatten_params(params))
        try:
            resp = self._http.post(self.base_url + REST_PATH, data=data)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise MoodleError(f"Eroare de retea la {wsfunction}: {exc}", function=wsfunction) from exc
        try:
            payload = resp.json()
        except ValueError as exc:
            raise MoodleError(f"Raspuns neasteptat la {wsfunction}: {resp.text[:200]}", function=wsfunction) from exc
        if isinstance(payload, dict) and "exception" in payload:
            raise MoodleError(payload.get("message", "eroare necunoscuta"), payload.get("errorcode"), wsfunction)
        return payload

    @property
    def siteinfo(self) -> dict[str, Any]:
        if self._siteinfo is None:
            self._siteinfo = self.call("core_webservice_get_site_info")
        return self._siteinfo

    @property
    def userid(self) -> int:
        return int(self.siteinfo["userid"])

    def available_functions(self) -> list[str]:
        return sorted(f["name"] for f in self.siteinfo.get("functions", []))

    def download(self, url: str, target: Path) -> int:
        """Descarca un fisier pluginfile (cu token). Scrie intai in .part, apoi redenumeste."""
        separator = "&" if "?" in url else "?"
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        size = 0
        try:
            with self._http.stream("GET", f"{url}{separator}token={self.token}") as resp:
                resp.raise_for_status()
                if "/login/" in str(resp.url):
                    raise MoodleError(f"Token sau sesiune invalida la descarcarea {target.name}")
                with partial.open("wb") as fh:
                    for chunk in resp.iter_bytes():
                        fh.write(chunk)
                        size += len(chunk)
        except httpx.HTTPError as exc:
            partial.unlink(missing_ok=True)
            raise MoodleError(f"Descarcare esuata pentru {target.name}: {exc}") from exc
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        partial.replace(target)
        return size

    def upload(self, path: Path, itemid: int = 0) -> dict[str, Any]:
        """Incarca un fisier in zona de ciorne (draft) a utilizatorului. Returneaza metadatele, inclusiv itemid."""
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as fh:
            try:
                resp = self._http.post(
                    self.base_url + UPLOAD_PATH,
                    data={"token": self.token, "filearea": "draft", "itemid": str(itemid)},
                    files={"file_1": (path.name, fh, mime)},
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise MoodleError(f"Incarcarea a esuat pentru {path.name}: {exc}") from exc
        payload = resp.json()
        if isinstance(payload, dict) and "exception" in payload:
            raise MoodleError(payload.get("message", "incarcare esuata"), payload.get("errorcode"))
        if not payload:
            raise MoodleError(f"Moodle nu a confirmat incarcarea pentru {path.name}")
        return payload[0]
