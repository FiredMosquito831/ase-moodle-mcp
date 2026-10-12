"""Quizuri Moodle: pornire incercare, citirea intrebarilor, salvare/trimitere raspunsuri si revizuire."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

from .actions import require_confirm
from .client import MoodleClient, MoodleError
from .text import html_to_text


class _InputParser(HTMLParser):
    """Extrage campurile de raspuns (input, textarea, select) dintr-un fragment de intrebare Moodle."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.inputs: list[dict[str, Any]] = []
        self.labels: dict[str, str] = {}
        self._label_for: str | None = None
        self._label_text: list[str] = []
        self._select: dict[str, Any] | None = None
        self._option: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if tag == "input" and a.get("name"):
            kind = (a.get("type") or "text").lower()
            if kind in ("submit", "button", "image", "reset"):
                return
            self.inputs.append({"name": a["name"], "type": kind, "value": a.get("value") or "", "id": a.get("id")})
        elif tag == "textarea" and a.get("name"):
            self.inputs.append({"name": a["name"], "type": "textarea", "value": "", "id": a.get("id")})
        elif tag == "select" and a.get("name"):
            self._select = {"name": a["name"], "type": "select", "value": "", "id": a.get("id"), "options": []}
            self.inputs.append(self._select)
        elif tag == "option" and self._select is not None:
            self._option = {"value": a.get("value") or "", "label": ""}
            self._select["options"].append(self._option)
        elif tag == "label" and a.get("for"):
            self._label_for = a["for"]
            self._label_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "label" and self._label_for is not None:
            self.labels[self._label_for] = " ".join("".join(self._label_text).split())
            self._label_for = None
        elif tag == "select":
            self._select = None
        elif tag == "option":
            self._option = None

    def handle_data(self, data: str) -> None:
        if self._label_for is not None:
            self._label_text.append(data)
        if self._option is not None:
            self._option["label"] += data


def parse_inputs(fragment: str | None) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Returneaza (campuri_de_raspuns, valori_ascunse). Radio/checkbox cu acelasi nume devin un singur camp."""
    parser = _InputParser()
    parser.feed(fragment or "")
    parser.close()

    answerable: list[dict[str, Any]] = []
    hidden: dict[str, str] = {}
    groups: dict[str, dict[str, Any]] = {}
    for item in parser.inputs:
        kind = item["type"]
        if kind == "hidden":
            hidden[item["name"]] = item["value"]
        elif kind in ("radio", "checkbox"):
            group = groups.get(item["name"])
            if group is None:
                group = {"name": item["name"], "type": kind, "options": []}
                groups[item["name"]] = group
                answerable.append(group)
            group["options"].append({"value": item["value"], "label": parser.labels.get(item["id"] or "", "")})
        elif kind == "select":
            options = [{"value": o["value"], "label": " ".join(o["label"].split())} for o in item["options"]]
            answerable.append({"name": item["name"], "type": "select", "options": options})
        else:
            answerable.append({"name": item["name"], "type": kind})
    return answerable, hidden


def start_attempt(client: MoodleClient, quiz_id: int, force_new: bool = False, confirm: bool = False) -> dict[str, Any]:
    """Porneste (sau reia) o incercare la un quiz."""
    require_confirm(confirm, f"incepe incercare la quiz {quiz_id}")
    resp = client.call("mod_quiz_start_attempt", {"quizid": quiz_id, "preflightdata": [], "forcenew": force_new})
    attempt = resp.get("attempt") or {}
    warnings = resp.get("warnings", [])
    if not attempt.get("id"):
        reason = "; ".join(w.get("message", "") for w in warnings) or "Moodle nu a returnat o incercare"
        raise MoodleError(f"Nu s-a putut porni incercarea la quiz {quiz_id}: {reason}", function="mod_quiz_start_attempt")
    return {
        "attempt_id": attempt.get("id"),
        "attempt": attempt.get("attempt"),
        "state": attempt.get("state"),
        "warnings": warnings,
    }


def attempt_questions(client: MoodleClient, attempt_id: int) -> dict[str, Any]:
    """Intrebarile unei incercari, cu campurile de raspuns (nume, tip, optiuni) si valorile ascunse."""
    questions: list[dict[str, Any]] = []
    hidden_all: dict[str, str] = {}
    page = -1
    attempt_state = None
    for _ in range(50):
        resp = client.call("mod_quiz_get_attempt_data", {"attemptid": attempt_id, "page": page})
        attempt_state = (resp.get("attempt") or {}).get("state", attempt_state)
        for q in resp.get("questions", []):
            inputs, hidden = parse_inputs(q.get("html"))
            hidden_all.update(hidden)
            questions.append({
                "slot": q.get("slot"),
                "type": q.get("type"),
                "text": html_to_text(q.get("html")),
                "inputs": inputs,
            })
        next_page = resp.get("nextpage", -1)
        if next_page is None or int(next_page) < 0 or int(next_page) == page:
            break
        page = int(next_page)
    return {
        "attempt_id": attempt_id,
        "state": attempt_state,
        "questions": questions,
        "_sequencechecks": {k: v for k, v in hidden_all.items() if ":sequencecheck" in k},
    }


def _answer_names(questions: dict[str, Any]) -> set[str]:
    names = set()
    for q in questions["questions"]:
        for field in q["inputs"]:
            names.add(field["name"])
    return names


def save_answers(
    client: MoodleClient,
    attempt_id: int,
    answers: dict[str, str],
    finish: bool = False,
    confirm: bool = False,
) -> dict[str, Any]:
    """Salveaza raspunsurile (finish=False) sau le trimite definitiv (finish=True).

    answers: {nume_camp: valoare}, unde nume_camp vine din attempt_questions()["questions"][i]["inputs"].
    """
    action = "trimitere FINALA" if finish else "salvare"
    require_confirm(confirm, f"{action} raspunsuri quiz, incercarea {attempt_id}")
    current = attempt_questions(client, attempt_id)
    valid = _answer_names(current)
    unknown = sorted(set(answers) - valid)
    if unknown:
        raise ValueError(f"Campuri necunoscute: {unknown}. Campuri valide: {sorted(valid)}")
    data = [{"name": k, "value": str(v)} for k, v in answers.items()]
    data += [{"name": k, "value": v} for k, v in current["_sequencechecks"].items() if k not in answers]
    resp = client.call("mod_quiz_process_attempt", {
        "attemptid": attempt_id,
        "data": data,
        "finishattempt": finish,
        "timeup": False,
    })
    return {
        "attempt_id": attempt_id,
        "finished": finish,
        "state": resp.get("state"),
        "warnings": resp.get("warnings", []),
    }


def review_attempt(client: MoodleClient, attempt_id: int) -> dict[str, Any]:
    """Revizuirea unei incercari terminate: intrebari, raspunsuri date si corectura (JSON Moodle brut)."""
    return client.call("mod_quiz_get_attempt_review", {"attemptid": attempt_id})
