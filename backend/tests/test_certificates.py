from datetime import date, timedelta

import pytest

from app.modules.alerts.service import today_ist
from app.core.words import date_in_words, rupees_in_words
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _setup(client, code):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])
    body = {"email": f"{code}-ravi@example.com".lower(), "full_name": "Ravi", "password": PASSWORD}
    ravi_id = (await client.post(f"{API}/teachers", json=body, headers=admin)).json()["id"]
    ravi = auth_headers((await login(client, body["email"], PASSWORD)).json()["access_token"])
    grade = (await client.post(f"{API}/classes", json={"name": "Grade 5", "section": "A", "academic_year": "2026", "class_teacher_id": ravi_id}, headers=admin)).json()
    asha = (
        await client.post(
            f"{API}/students",
            json={
                "admission_number": "A-1", "full_name": "Asha Rao", "class_id": grade["id"], "date_of_birth": "2016-04-12",
                "gender": "female", "blood_group": "B+", "admission_date": "2021-06-01", "address": "12 MG Road",
                "father": {"full_name": "Srinivas Rao", "phone": "9848022338"}, "mother": {"full_name": "Padma Rao", "phone": "9848022339"},
            },
            headers=admin,
        )
    ).json()
    assert "id" in asha, asha
    return {"admin": admin, "ravi": ravi, "grade": grade, "asha": asha}


@pytest.mark.parametrize(
    ("value", "words"),
    [
        (date(2016, 4, 12), "Twelfth April Two Thousand Sixteen"),
        (date(2009, 11, 21), "Twenty-First November Two Thousand Nine"),
        (date(1999, 1, 30), "Thirtieth January One Thousand Nine Hundred Ninety-Nine"),
    ],
)
def test_date_in_words(value, words):
    assert date_in_words(value) == words


@pytest.mark.parametrize(
    ("amount", "words"),
    [
        (25000, "Rupees Twenty-Five Thousand Only"),
        (125000.5, "Rupees One Lakh Twenty-Five Thousand and Fifty Paise Only"),
        (12345678, "Rupees One Crore Twenty-Three Lakh Forty-Five Thousand Six Hundred Seventy-Eight Only"),
        (0, "Rupees Zero Only"),
    ],
)
def test_rupees_in_words(amount, words):
    assert rupees_in_words(amount) == words


async def test_tc_snapshot_serial_and_student_left(db, client):
    ctx = await _setup(client, "CER1")
    yesterday = (today_ist() - timedelta(days=1)).isoformat()
    await client.post(f"{API}/classes/{ctx['grade']['id']}/attendance", json={"date": yesterday, "records": [{"student_id": ctx["asha"]["id"], "status": "present"}]}, headers=ctx["ravi"])

    response = await client.post(f"{API}/students/{ctx['asha']['id']}/certificates", json={"kind": "tc", "reason": "Family moving to Pune", "promotion": "Yes, to Grade 6"}, headers=ctx["admin"])
    assert response.status_code == 201, response.text
    tc = response.json()
    assert tc["serial_no"] == f"TC/{today_ist().year}/0001" and tc["title"] == "Transfer Certificate"
    d = tc["details"]
    assert (d["student_name"], d["father_name"], d["mother_name"], d["class_name"]) == ("Asha Rao", "Srinivas Rao", "Padma Rao", "Grade 5 - A")
    assert (d["date_of_birth_words"], d["working_days"], d["days_present"], d["reason"]) == ("Twelfth April Two Thousand Sixteen", 1, 1, "Family moving to Pune")
    assert tc["school"]["code"] == "CER1"

    student = (await client.get(f"{API}/students/{ctx['asha']['id']}", headers=ctx["admin"])).json()
    assert student["status"] == "left"
    # One live TC per student; a bonafide is only for current students.
    again = await client.post(f"{API}/students/{ctx['asha']['id']}/certificates", json={"kind": "tc"}, headers=ctx["admin"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "tc_exists"
    assert (await client.post(f"{API}/students/{ctx['asha']['id']}/certificates", json={"kind": "bonafide"}, headers=ctx["admin"])).status_code == 409

    # Cancelling frees the student for a corrected TC; the serial moves on.
    cancelled = await client.post(f"{API}/certificates/{tc['id']}/cancel", json={"reason": "Wrong leaving date"}, headers=ctx["admin"])
    assert cancelled.json()["cancelled"] is True
    second = (await client.post(f"{API}/students/{ctx['asha']['id']}/certificates", json={"kind": "tc"}, headers=ctx["admin"])).json()
    assert second["serial_no"].endswith("/0002")
    listed = (await client.get(f"{API}/students/{ctx['asha']['id']}/certificates", headers=ctx["admin"])).json()
    assert [c["serial_no"][-4:] for c in listed] == ["0002", "0001"]


async def test_bonafide_and_access(db, client):
    ctx = await _setup(client, "CER2")
    response = await client.post(f"{API}/students/{ctx['asha']['id']}/certificates", json={"kind": "bonafide", "purpose": "Bank account opening"}, headers=ctx["admin"])
    bonafide = response.json()
    assert bonafide["serial_no"] == f"BON/{today_ist().year}/0001" and bonafide["details"]["purpose"] == "Bank account opening"
    assert (await client.get(f"{API}/students/{ctx['asha']['id']}", headers=ctx["admin"])).json()["status"] == "active"

    assert (await client.post(f"{API}/students/{ctx['asha']['id']}/certificates", json={"kind": "tc"}, headers=ctx["ravi"])).status_code == 403
    assert (await client.get(f"{API}/certificates/{bonafide['id']}", headers=ctx["ravi"])).status_code == 403
    future = (today_ist() + timedelta(days=3)).isoformat()
    assert (await client.post(f"{API}/students/{ctx['asha']['id']}/certificates", json={"kind": "tc", "leaving_date": future}, headers=ctx["admin"])).status_code == 400

    other = await _setup(client, "CER3")
    assert (await client.get(f"{API}/certificates/{bonafide['id']}", headers=other["admin"])).status_code == 404
    assert (await client.post(f"{API}/students/{ctx['asha']['id']}/certificates", json={"kind": "bonafide"}, headers=other["admin"])).status_code == 404


async def test_id_cards_for_a_class(db, client):
    ctx = await _setup(client, "CER4")
    sheet = (await client.get(f"{API}/id-cards", params={"class_id": ctx["grade"]["id"]}, headers=ctx["admin"])).json()
    assert sheet["academic_year"] == "2026" and sheet["school"]["name"]
    card = sheet["cards"][0]
    assert (card["full_name"], card["class_label"], card["blood_group"], card["parent_name"], card["parent_phone"]) == (
        "Asha Rao", "Grade 5 - A", "B+", "Srinivas Rao", "9848022338",
    )
    assert card["qr_text"] == "CER4:A-1" and card["has_photo"] is False
    assert (await client.get(f"{API}/id-cards", params={"class_id": ctx["grade"]["id"]}, headers=ctx["ravi"])).status_code == 403
