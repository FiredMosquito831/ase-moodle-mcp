"""Lista functiilor Moodle (web service) pe care le foloseste pachetul. `doctor` o compara cu site-ul.

Testul tests/test_moodle_functions.py cauta numele in src/ase_moodle si pica daca unul lipseste de aici
(sau daca aici ramane un nume nefolosit). Cand adaugi un apel Moodle nou, adauga-l si aici.

- REQUIRED: fara ele o unealta (CLI/MCP) nu merge.
- OPTIONAL: codul merge si fara ele:
  - mod_forum_get_forum_discussions_paginated: rezerva pentru site-uri fara mod_forum_get_forum_discussions
    (scoasa in Moodle 4.5);
  - listele de module din materials.MODULE_LISTERS folosite doar la descarcare (pagini, carti, chat, survey...):
    ModuleIndex prinde eroarea si pune un avertisment, restul cursului se descarca. Moodle 5.0 scoate
    mod_chat si mod_survey. assign/forum/quiz sunt obligatorii, pentru ca le folosesc si uneltele de citire.
"""

from __future__ import annotations

from typing import Iterable

REQUIRED_FUNCTIONS: tuple[str, ...] = (
    # site, cursuri, structura
    "core_webservice_get_site_info",
    "core_enrol_get_users_courses",
    "core_course_get_courses_by_field",
    "core_course_get_contents",
    "core_calendar_get_action_events_by_timesort",
    # teme
    "mod_assign_get_assignments",
    "mod_assign_get_submission_status",
    "mod_assign_save_submission",
    "mod_assign_submit_for_grading",
    # forumuri
    "mod_forum_get_forums_by_courses",
    "mod_forum_get_forum_discussions",
    "mod_forum_get_discussion_posts",
    "mod_forum_add_discussion_post",
    "mod_forum_add_discussion",
    # note
    "gradereport_user_get_grades_table",
    "gradereport_overview_get_course_grades",
    # quizuri
    "mod_quiz_get_quizzes_by_courses",
    "mod_quiz_get_user_attempts",
    "mod_quiz_start_attempt",
    "mod_quiz_get_attempt_data",
    "mod_quiz_process_attempt",
    "mod_quiz_get_attempt_review",
    # notificari
    "message_popup_get_popup_notifications",
    "core_message_mark_notification_read",
)

OPTIONAL_FUNCTIONS: tuple[str, ...] = (
    "mod_forum_get_forum_discussions_paginated",
    "mod_page_get_pages_by_courses",
    "mod_book_get_books_by_courses",
    "mod_lesson_get_lessons_by_courses",
    "mod_glossary_get_glossaries_by_courses",
    "mod_wiki_get_wikis_by_courses",
    "mod_data_get_databases_by_courses",
    "mod_choice_get_choices_by_courses",
    "mod_feedback_get_feedbacks_by_courses",
    "mod_survey_get_surveys_by_courses",
    "mod_workshop_get_workshops_by_courses",
    "mod_h5pactivity_get_h5pactivities_by_courses",
    "mod_scorm_get_scorms_by_courses",
    "mod_url_get_urls_by_courses",
    "mod_folder_get_folders_by_courses",
    "mod_resource_get_resources_by_courses",
    "mod_label_get_labels_by_courses",
    "mod_chat_get_chats_by_courses",
    "mod_imscp_get_imscps_by_courses",
    "mod_lti_get_ltis_by_courses",
)


def missing_functions(available: Iterable[str]) -> tuple[list[str], list[str]]:
    """(obligatorii lipsa, optionale lipsa), in ordinea din liste."""
    present = set(available)
    return (
        [name for name in REQUIRED_FUNCTIONS if name not in present],
        [name for name in OPTIONAL_FUNCTIONS if name not in present],
    )
