from flask import Blueprint, redirect, render_template, request

from .extensions import db
from .models import Discipline, GroupDisciplineSelection, StudyGroup
from .services import ensure_storage_ready

web_bp = Blueprint("web", __name__)

SUBJECT_OPTIONS = {
    "math": "Математика",
    "physics": "Физика",
    "programming": "Программирование",
    "algorithms": "Алгоритмы и структуры данных",
    "databases": "Базы данных",
    "networks": "Компьютерные сети",
    "english": "Английский язык",
    "economics": "Экономика",
}

TERM_BY_FORM_VALUE = {
    "aut25": "Осень 2025",
    "spr26": "Весна 2026",
}

FORM_VALUE_BY_TERM = {term: value for value, term in TERM_BY_FORM_VALUE.items()}


@web_bp.route("/", methods=["GET", "POST"])
def index():
    ensure_storage_ready()
    groups = list(StudyGroup.query.order_by(StudyGroup.group_number))

    if request.method == "POST":
        save_recommended_groups(groups)
        return redirect("./")

    return render_template(
        "index.html",
        groups=[recommended_group_payload(group) for group in groups],
        group_subjects=selected_subject_values(groups),
    )


def recommended_group_payload(group: StudyGroup) -> dict:
    return {
        "id": group.group_number,
        "course": group.course,
        "prev": [
            False,
            group.participation_status == "yes",
            bool(group.tests),
        ],
        "current": group.current_testing,
        "plan": FORM_VALUE_BY_TERM.get(group.planned_term, ""),
    }


def selected_subject_values(groups: list[StudyGroup]) -> dict[str, list[str]]:
    subject_by_name = {name: value for value, name in SUBJECT_OPTIONS.items()}
    values_by_group = {}

    for group in groups:
        values = [
            subject_by_name[selection.discipline.name]
            for selection in group.selected_disciplines
            if selection.discipline.name in subject_by_name
        ]
        if values:
            values_by_group[group.group_number] = (values + [""])[:2]

    return values_by_group


def save_recommended_groups(groups: list[StudyGroup]) -> None:
    for group in groups:
        group_key = group.group_number
        plan_value = request.form.get(f"plan_{group_key}")
        group.current_testing = f"cur_{group_key}" in request.form
        group.planned_term = TERM_BY_FORM_VALUE.get(plan_value)

        GroupDisciplineSelection.query.filter_by(group_id=group.id).delete()
        if group.planned_term:
            subject_values = [
                request.form.get(f"subjects_{group_key}_1", ""),
                request.form.get(f"subjects_{group_key}_2", ""),
            ]
            for subject_value in dict.fromkeys(subject_values):
                if subject_value not in SUBJECT_OPTIONS:
                    continue
                discipline = ensure_discipline(SUBJECT_OPTIONS[subject_value])
                db.session.add(GroupDisciplineSelection(group=group, discipline=discipline))

    db.session.commit()


def ensure_discipline(name: str) -> Discipline:
    discipline = Discipline.query.filter_by(name=name).first()
    if discipline is None:
        discipline = Discipline(name=name, department="ФИТ")
        db.session.add(discipline)
        db.session.flush()
    return discipline
