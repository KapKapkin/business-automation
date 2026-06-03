def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "OK"}


def test_main_screen_uses_copied_recommended_groups_design(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Формирование списка рекомендуемых групп" in html
    assert 'class="panel"' in html
    assert 'class="groups"' in html
    assert 'id="subjectModal"' in html
    assert "static/style.css" in html


def test_recommended_groups_form_saves_plan_and_subjects(client, app):
    response = client.post(
        "/",
        data={
            "cur_221-112": "on",
            "plan_221-112": "aut25",
            "subjects_221-112_1": "math",
            "subjects_221-112_2": "databases",
        },
    )

    assert response.status_code == 302

    with app.app_context():
        from app.models import StudyGroup

        group = StudyGroup.query.filter_by(group_number="221-112").one()
        assert group.current_testing is True
        assert group.planned_term == "Осень 2025"
        assert sorted(selection.discipline.name for selection in group.selected_disciplines) == [
            "Базы данных",
            "Математика",
        ]


def test_bootstrap_exposes_python_task_data(client):
    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    payload = response.get_json()
    assert [tab["label"] for tab in payload["tabs"]] == [
        "Преподаватель",
        "ЛПР",
        "Заведующий кафедрой",
    ]
    assert payload["groups"]
    assert payload["disciplines"]
    assert payload["reports"]
    assert payload["tests"]
    assert payload["experts"]


def test_leader_can_save_group_participation(client):
    group_id = client.get("/api/groups").get_json()[0]["id"]

    response = client.post(
        f"/api/groups/{group_id}/participation",
        json={"status": "yes"},
        headers={"X-Role": "leader"},
    )

    assert response.status_code == 200
    assert response.get_json()["participationStatus"] == "yes"


def test_non_leader_cannot_save_group_participation(client):
    group_id = client.get("/api/groups").get_json()[0]["id"]

    response = client.post(
        f"/api/groups/{group_id}/participation",
        json={"status": "yes"},
        headers={"X-Role": "teacher"},
    )

    assert response.status_code == 403


def test_can_save_selected_disciplines(client):
    bootstrap = client.get("/api/bootstrap").get_json()
    group_id = bootstrap["groups"][0]["id"]
    discipline_id = bootstrap["disciplines"][0]["id"]

    response = client.put(
        f"/api/groups/{group_id}/disciplines",
        json={"disciplineIds": [discipline_id]},
        headers={"X-Role": "leader"},
    )

    assert response.status_code == 200
    assert response.get_json()["selectedDisciplines"] == [
        {"id": discipline_id, "name": bootstrap["disciplines"][0]["name"]}
    ]


def test_report_upload_locks_and_lpr_reject_unlocks(client, tmp_path):
    report_id = client.get("/api/reports").get_json()[0]["id"]
    report_file = tmp_path / "report.txt"
    report_file.write_text("report body", encoding="utf-8")

    with report_file.open("rb") as file_obj:
        upload = client.post(
            f"/api/reports/{report_id}/upload",
            data={"file": (file_obj, "report.txt")},
            content_type="multipart/form-data",
        )

    assert upload.status_code == 200
    uploaded = upload.get_json()
    assert uploaded["status"] == "Отправлен на проверку ЛПР"
    assert uploaded["uploadLocked"] is True

    decision = client.post(
        f"/api/reports/{report_id}/lpr-decision",
        json={"action": "reject", "comment": "Исправить"},
        headers={"X-Role": "leader"},
    )

    assert decision.status_code == 200
    rejected = decision.get_json()
    assert rejected["status"] == "На доработке"
    assert rejected["uploadLocked"] is False
