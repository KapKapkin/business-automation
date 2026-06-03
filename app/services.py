from datetime import date, time
from threading import Lock

from flask import current_app

from .extensions import db
from .models import (
    Discipline,
    ExpertResponsibility,
    GroupDisciplineSelection,
    KnowledgeTest,
    Report,
    StudyGroup,
)

EXTERNAL_GROUP_SOURCE = [
    {"group_number": "221-111", "course": 3},
    {"group_number": "221-112", "course": 3},
    {"group_number": "221-113", "course": 3},
    {"group_number": "221-114", "course": 3},
]

DEFAULT_DISCIPLINES = [
    {"name": "Сети и телекоммуникации", "department": "Кафедра информационной безопасности"},
    {"name": "Back-end разработка", "department": "Кафедра инфокогнитивных технологий"},
    {"name": "Базы данных", "department": "Кафедра прикладной информатики"},
]

_storage_lock = Lock()


def ensure_storage_ready() -> None:
    if current_app.config.get("_STORAGE_READY"):
        return
    with _storage_lock:
        if current_app.config.get("_STORAGE_READY"):
            return
        db.create_all()
        ensure_demo_data()
        current_app.config["_STORAGE_READY"] = True


def sync_external_groups() -> list[StudyGroup]:
    groups = []
    for item in EXTERNAL_GROUP_SOURCE:
        group = StudyGroup.query.filter_by(group_number=item["group_number"]).first()
        if group is None:
            group = StudyGroup(
                group_number=item["group_number"],
                course=item["course"],
                participation_status="no",
            )
            db.session.add(group)
        else:
            group.course = item["course"]
        groups.append(group)
    db.session.commit()
    return groups


def ensure_demo_data() -> None:
    sync_external_groups()

    for item in DEFAULT_DISCIPLINES:
        discipline = Discipline.query.filter_by(name=item["name"]).first()
        if discipline is None:
            db.session.add(Discipline(**item))
    db.session.commit()

    if GroupDisciplineSelection.query.count() == 0:
        group = StudyGroup.query.filter_by(group_number="221-111").first()
        disciplines = Discipline.query.order_by(Discipline.id).limit(2).all()
        for discipline in disciplines:
            db.session.add(GroupDisciplineSelection(group=group, discipline=discipline))
        group.participation_status = "yes"
        group.planned_term = "Весна 2026"
        group.current_testing = True
        db.session.commit()

    if KnowledgeTest.query.count() == 0:
        group = StudyGroup.query.filter_by(group_number="221-111").first()
        discipline = Discipline.query.filter_by(name="Сети и телекоммуникации").first()
        db.session.add(
            KnowledgeTest(
                group=group,
                discipline=discipline,
                teacher_name="Иванов Иван Иванович",
                profile="Информационные системы и технологии",
                scheduled_date=date(2026, 6, 15),
                scheduled_time=time(12, 20),
                agreement_status="Согласовано",
            )
        )
        db.session.commit()

    if Report.query.count() == 0:
        group = StudyGroup.query.filter_by(group_number="221-111").first()
        disciplines = Discipline.query.order_by(Discipline.id).limit(2).all()
        statuses = ["отчёт составлен", "На проверке"]
        for discipline, status in zip(disciplines, statuses, strict=False):
            db.session.add(Report(group=group, discipline=discipline, status=status))
        db.session.commit()

    if ExpertResponsibility.query.count() == 0:
        db.session.add_all(
            [
                ExpertResponsibility(
                    full_name="Петрова Мария Ивановна",
                    position="Ответственный эксперт",
                    indicator="Проверка отчетов по ИТ-направлениям",
                    access_open=True,
                ),
                ExpertResponsibility(
                    full_name="Сидоров Алексей Павлович",
                    position="Эксперт",
                    indicator="Согласование графика проверок",
                    access_open=False,
                ),
            ]
        )
        db.session.commit()
