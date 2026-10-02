"""Fee reminders, result alerts and the MSG91 WhatsApp sender."""

from app.integrations import sms
from app.integrations.sms import Msg91WhatsAppSender, SmsResult
from app.modules.alerts import service as alerts
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


class FakeSender:
    def __init__(self):
        self.sent = []

    async def send(self, phone, message, kind, variables):
        self.sent.append((phone, kind, variables))
        return SmsResult("sent", "", "m1")


async def _college(client, code):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    admin = auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])
    faculty = (await client.post(f"{API}/teachers", json={"email": f"{code}-f@example.com".lower(), "full_name": "Ravi", "password": PASSWORD}, headers=admin)).json()
    batch = (await client.post(f"{API}/classes", json={"name": "B.Sc", "section": "A", "academic_year": "2026", "class_teacher_id": faculty["id"]}, headers=admin)).json()
    body = {"admission_number": "S1", "full_name": "Asha", "class_id": batch["id"], "primary_contact": "father",
            "father": {"full_name": "Raju", "phone": "9876543210"}}
    student = await client.post(f"{API}/students", json=body, headers=admin)
    assert student.status_code == 201, student.text
    return admin, batch, student.json()


async def test_results_published_alert(db, client, monkeypatch):
    fake = FakeSender()
    monkeypatch.setattr(alerts, "get_sms_sender", lambda: fake)
    admin, batch, asha = await _college(client, "RES9")
    maths = (await client.post(f"{API}/subjects", json={"name": "Maths", "credits": 4}, headers=admin)).json()
    faculty_id = (await client.get(f"{API}/teachers", headers=admin)).json()[0]["id"]
    await client.put(f"{API}/classes/{batch['id']}/subjects/{maths['id']}", json={"teacher_id": faculty_id}, headers=admin)
    exam = (await client.post(f"{API}/exams", json={"name": "Sem 1", "exam_type": "semester", "academic_year": "2026", "class_ids": [batch["id"]],
                                                     "max_marks": "100", "pass_marks": "40"}, headers=admin)).json()
    await client.put(f"{API}/exam-papers/{exam['papers'][0]['id']}/marks", json={"entries": [{"student_id": asha["id"], "marks": "92"}]}, headers=admin)
    await client.post(f"{API}/exams/{exam['id']}/publish", headers=admin)
    assert [(k, v["exam"], v["result"]) for _, k, v in fake.sent] == [("result", "Sem 1", "SGPA 10.0, all passed")]
    # Unpublish and publish again: no second message.
    await client.post(f"{API}/exams/{exam['id']}/unpublish", headers=admin)
    await client.post(f"{API}/exams/{exam['id']}/publish", headers=admin)
    assert len(fake.sent) == 1


async def test_whatsapp_payload_and_both_channels(monkeypatch):
    sender = Msg91WhatsAppSender("key", "919000000000", "en", {"absence": "absent_alert"})
    body = sender.body("919876543210", "absence", {"student": "Asha", "class": "B.Sc A", "date": "01 Sep 2026", "school": "ANV College"})
    template = body["payload"]["template"]
    assert (body["integrated_number"], template["name"], template["to_and_components"][0]["to"]) == ("919000000000", "absent_alert", ["919876543210"])
    assert template["to_and_components"][0]["components"]["body_1"] == {"type": "text", "value": "Asha"}
    assert (await sender.send("9876543210", "", "fee", {})).status == "not_sent"  # no template for fee

    posted = []
    monkeypatch.setattr(sender, "_post", lambda b: posted.append(b) or {"status": "success", "request_id": "r1"})
    result = await sender.send("98765 43210", "", "absence", {"student": "Asha"})
    assert (result.status, result.message_id, posted[0]["payload"]["template"]["to_and_components"][0]["to"]) == ("sent", "r1", ["919876543210"])
    assert sms.get_whatsapp_sender() is None  # off by default
