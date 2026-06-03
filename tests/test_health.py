def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "OK"}


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
