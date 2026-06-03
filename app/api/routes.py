import csv
import io
import os
from datetime import datetime

from flask import current_app, jsonify, request, send_file
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import (
    Discipline,
    ExpertResponsibility,
    GroupDisciplineSelection,
    KnowledgeTest,
    Report,
    StudyGroup,
)
from ..services import ensure_storage_ready, sync_external_groups
from . import api_bp


def require_leader_role():
    role = request.headers.get("X-Role", "leader")
    if role != "leader":
        return jsonify({"error": "Forbidden"}), 403
    return None


def group_payload(group: StudyGroup) -> dict:
    return {
        "id": group.id,
        "groupNumber": group.group_number,
        "course": group.course,
        "participationStatus": group.participation_status,
        "plannedTerm": group.planned_term,
        "currentTesting": group.current_testing,
        "selectedDisciplines": [
            {
                "id": item.discipline.id,
                "name": item.discipline.name,
            }
            for item in group.selected_disciplines
        ],
    }


def report_payload(report: Report) -> dict:
    return {
        "id": report.id,
        "group": report.group.group_number,
        "discipline": report.discipline.name,
        "status": report.status,
        "originalFilename": report.original_filename,
        "uploadLocked": report.upload_locked,
        "uploadedAt": report.uploaded_at.isoformat() if report.uploaded_at else None,
        "lprComment": report.lpr_comment,
        "downloadUrl": f"api/reports/{report.id}/download" if report.file_path else None,
    }


def test_payload(test: KnowledgeTest) -> dict:
    return {
        "id": test.id,
        "group": test.group.group_number,
        "profile": test.profile,
        "discipline": test.discipline.name,
        "department": test.discipline.department,
        "teacherName": test.teacher_name,
        "date": test.scheduled_date.isoformat(),
        "time": test.scheduled_time.strftime("%H:%M"),
        "agreementStatus": test.agreement_status,
    }


@api_bp.get("/health")
def health():
    return jsonify({"status": "OK"})


@api_bp.get("/bootstrap")
def bootstrap():
    ensure_storage_ready()
    return jsonify(
        {
            "groups": [group_payload(group) for group in StudyGroup.query.order_by(StudyGroup.group_number)],
            "disciplines": [
                {
                    "id": discipline.id,
                    "name": discipline.name,
                    "department": discipline.department,
                }
                for discipline in Discipline.query.order_by(Discipline.name)
            ],
            "tests": [test_payload(test) for test in KnowledgeTest.query.order_by(KnowledgeTest.scheduled_date)],
            "reports": [report_payload(report) for report in Report.query.order_by(Report.id)],
            "experts": [
                {
                    "id": expert.id,
                    "fullName": expert.full_name,
                    "position": expert.position,
                    "indicator": expert.indicator,
                    "accessOpen": expert.access_open,
                }
                for expert in ExpertResponsibility.query.order_by(ExpertResponsibility.full_name)
            ],
            "tabs": [
                {"id": "teacher", "label": "Преподаватель"},
                {"id": "lpr", "label": "ЛПР"},
                {"id": "head", "label": "Заведующий кафедрой"},
            ],
        }
    )


@api_bp.get("/groups")
def get_groups():
    ensure_storage_ready()
    return jsonify([group_payload(group) for group in StudyGroup.query.order_by(StudyGroup.group_number)])


@api_bp.post("/groups/sync")
def sync_groups():
    ensure_storage_ready()
    role_error = require_leader_role()
    if role_error:
        return role_error
    groups = sync_external_groups()
    return jsonify([group_payload(group) for group in groups])


@api_bp.post("/groups/<int:group_id>/participation")
def save_group_participation(group_id: int):
    ensure_storage_ready()
    role_error = require_leader_role()
    if role_error:
        return role_error
    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    if status not in {"yes", "no"}:
        return jsonify({"error": 'status must be "yes" or "no"'}), 400

    group = db.session.get(StudyGroup, group_id)
    if group is None:
        return jsonify({"error": "Group not found"}), 404

    was_empty = group.participation_status not in {"yes", "no"}
    group.participation_status = status
    db.session.commit()
    return jsonify(group_payload(group)), 201 if was_empty else 200


@api_bp.put("/groups/<int:group_id>/disciplines")
def save_group_disciplines(group_id: int):
    ensure_storage_ready()
    role_error = require_leader_role()
    if role_error:
        return role_error
    payload = request.get_json(silent=True) or {}
    discipline_ids = payload.get("disciplineIds")
    if not isinstance(discipline_ids, list):
        return jsonify({"error": "disciplineIds must be a list"}), 400

    group = db.session.get(StudyGroup, group_id)
    if group is None:
        return jsonify({"error": "Group not found"}), 404

    Discipline.query.filter(Discipline.id.in_(discipline_ids)).all()
    found_ids = {discipline.id for discipline in Discipline.query.filter(Discipline.id.in_(discipline_ids)).all()}
    missing_ids = sorted(set(discipline_ids) - found_ids)
    if missing_ids:
        return jsonify({"error": "Disciplines not found", "ids": missing_ids}), 404

    GroupDisciplineSelection.query.filter_by(group_id=group.id).delete()
    for discipline_id in sorted(found_ids):
        db.session.add(GroupDisciplineSelection(group_id=group.id, discipline_id=discipline_id))
    db.session.commit()
    return jsonify(group_payload(group))


@api_bp.post("/groups/<int:group_id>/plan")
def save_group_plan(group_id: int):
    ensure_storage_ready()
    role_error = require_leader_role()
    if role_error:
        return role_error
    payload = request.get_json(silent=True) or {}
    group = db.session.get(StudyGroup, group_id)
    if group is None:
        return jsonify({"error": "Group not found"}), 404
    group.current_testing = bool(payload.get("currentTesting"))
    group.planned_term = payload.get("plannedTerm") or None
    db.session.commit()
    return jsonify(group_payload(group))


@api_bp.get("/reports")
def get_reports():
    ensure_storage_ready()
    return jsonify([report_payload(report) for report in Report.query.order_by(Report.id)])


@api_bp.post("/reports/<int:report_id>/upload")
def upload_report(report_id: int):
    ensure_storage_ready()
    report = db.session.get(Report, report_id)
    if report is None:
        return jsonify({"error": "Report not found"}), 404
    if report.upload_locked:
        return jsonify({"error": "Report upload is locked"}), 403
    if "file" not in request.files:
        return jsonify({"error": "File is required"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "File is required"}), 400

    upload_dir = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_dir, exist_ok=True)
    filename = secure_filename(file.filename)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    stored_name = f"report_{report.id}_{timestamp}_{filename}"
    path = os.path.join(upload_dir, stored_name)
    file.save(path)

    report.file_path = path
    report.original_filename = file.filename
    report.uploaded_at = datetime.utcnow()
    report.status = "Отправлен на проверку ЛПР"
    report.upload_locked = True
    db.session.commit()

    return jsonify(report_payload(report))


@api_bp.get("/reports/<int:report_id>/download")
def download_report(report_id: int):
    ensure_storage_ready()
    report = db.session.get(Report, report_id)
    if report is None or not report.file_path:
        return jsonify({"error": "Report file not found"}), 404
    return send_file(report.file_path, as_attachment=True, download_name=report.original_filename)


@api_bp.post("/reports/<int:report_id>/lpr-decision")
def lpr_decision(report_id: int):
    ensure_storage_ready()
    role_error = require_leader_role()
    if role_error:
        return role_error
    payload = request.get_json(silent=True) or {}
    action = payload.get("action")
    if action not in {"approve", "reject"}:
        return jsonify({"error": 'action must be "approve" or "reject"'}), 400

    report = db.session.get(Report, report_id)
    if report is None:
        return jsonify({"error": "Report not found"}), 404
    report.status = "Сдан" if action == "approve" else "На доработке"
    report.lpr_comment = payload.get("comment")
    if action == "reject":
        report.upload_locked = False
    db.session.commit()
    return jsonify(report_payload(report))


@api_bp.get("/schedule/export")
def export_schedule():
    ensure_storage_ready()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Группа", "Профиль", "Дисциплина", "Кафедра", "Преподаватель", "Дата", "Время"])
    for item in KnowledgeTest.query.order_by(KnowledgeTest.scheduled_date):
        writer.writerow(
            [
                item.group.group_number,
                item.profile,
                item.discipline.name,
                item.discipline.department,
                item.teacher_name,
                item.scheduled_date.strftime("%d.%m.%Y"),
                item.scheduled_time.strftime("%H:%M"),
            ]
        )
    buffer = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    return send_file(buffer, mimetype="text/csv", as_attachment=True, download_name="grafik_proverki.csv")


@api_bp.post("/experts/<int:expert_id>/access")
def update_expert_access(expert_id: int):
    ensure_storage_ready()
    role_error = require_leader_role()
    if role_error:
        return role_error
    payload = request.get_json(silent=True) or {}
    expert = db.session.get(ExpertResponsibility, expert_id)
    if expert is None:
        return jsonify({"error": "Expert not found"}), 404
    expert.access_open = bool(payload.get("accessOpen"))
    expert.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(
        {
            "id": expert.id,
            "fullName": expert.full_name,
            "position": expert.position,
            "indicator": expert.indicator,
            "accessOpen": expert.access_open,
        }
    )
