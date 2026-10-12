"""Cursurile inscrise: an de studiu, semestru, tip (CURS/SEMINAR/LABORATOR) si an universitar."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Iterable

from .client import MoodleClient
from .text import html_to_text

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}
TIP_ALIASES = {"C": "CURS", "CURS": "CURS", "S": "SEMINAR", "SEMINAR": "SEMINAR", "L/P": "LABORATOR", "L": "LABORATOR"}


@dataclass
class Course:
    id: int
    shortname: str
    fullname: str
    name: str  # materia, fara tip si semestru
    tip: str | None  # CURS, SEMINAR, LABORATOR (sau valoarea originala)
    semester: int | None
    academic_year: str | None  # ex. 2026-2027
    study_year: int | None  # anul de studiu (1, 2, 3...)
    study_year_source: str | None  # "descriere", "dedus din aceeasi materie" sau None
    category: str
    summary: str
    startdate: int
    enddate: int

    def to_dict(self) -> dict:
        return asdict(self)


def parse_course(raw: dict) -> Course:
    """Extrage an, semestru si tip din numele Moodle si anul de studiu din descrierea cursului."""
    fullname = raw.get("fullname") or raw.get("displayname") or ""
    tip_match = re.search(r"Tip-([^,]+)", fullname)
    sem_match = re.search(r"Sem-(\d)", fullname)
    year_match = re.search(r"\((\d{4}-\d{4})\)", fullname)
    summary = html_to_text(raw.get("summary"))
    anul = re.search(r"Anul\s+(\d+|[IVX]+)\b", summary)

    study_year = None
    if anul:
        value = anul.group(1)
        study_year = int(value) if value.isdigit() else ROMAN.get(value)

    tip = None
    if tip_match:
        raw_tip = tip_match.group(1).strip().upper()
        tip = TIP_ALIASES.get(raw_tip, raw_tip)

    return Course(
        id=int(raw["id"]),
        shortname=raw.get("shortname", ""),
        fullname=fullname,
        name=re.split(r",\s*Tip-", fullname)[0].strip(),
        tip=tip,
        semester=int(sem_match.group(1)) if sem_match else None,
        academic_year=year_match.group(1) if year_match else None,
        study_year=study_year,
        study_year_source="descriere" if study_year else None,
        category=raw.get("categoryname", ""),
        summary=summary,
        startdate=int(raw.get("startdate") or 0),
        enddate=int(raw.get("enddate") or 0),
    )


def _infer_missing_years(courses: list[Course]) -> None:
    """Cursurile fara 'Anul N' in descriere primesc anul de la alt curs cu aceeasi materie."""
    known: dict[str, int] = {}
    for course in courses:
        if course.study_year:
            known.setdefault(course.name, course.study_year)
    for course in courses:
        if course.study_year is None and course.name in known:
            course.study_year = known[course.name]
            course.study_year_source = "dedus din aceeasi materie"


def fetch_courses(client: MoodleClient) -> list[Course]:
    """Toate cursurile la care utilizatorul este inscris, sortate dupa an universitar, semestru si materie."""
    enrolled = client.call("core_enrol_get_users_courses", {"userid": client.userid})
    ids = [int(item["id"]) for item in enrolled]
    if not ids:
        return []
    raw_courses = client.call("core_course_get_courses_by_field", {"field": "ids", "value": ",".join(map(str, ids))})
    courses = [parse_course(item) for item in raw_courses.get("courses", [])]
    _infer_missing_years(courses)
    return sorted(courses, key=lambda c: (c.academic_year or "", c.semester or 0, c.name, c.tip or ""))


def filter_courses(
    courses: Iterable[Course],
    study_year: int | None = None,
    semester: int | None = None,
    academic_year: str | None = None,
    tip: str | None = None,
    search: str | None = None,
) -> list[Course]:
    result = []
    wanted_tip = TIP_ALIASES.get((tip or "").upper(), (tip or "").upper()) if tip else None
    for course in courses:
        if study_year is not None and course.study_year != study_year:
            continue
        if semester is not None and course.semester != semester:
            continue
        if academic_year and course.academic_year != academic_year:
            continue
        if wanted_tip and course.tip != wanted_tip:
            continue
        if search and search.lower() not in course.fullname.lower():
            continue
        result.append(course)
    return result
