from datetime import timedelta

from app.modules.alerts.service import today_ist
from tests.test_parents import API, _parent_headers, _school, _student

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
FEE = {"academic_year": "2026", "due_date": "2026-12-01"}


async def _family(client, code, phone):
    class_id, admin = await _school(client, code)
    asha = await _student(client, admin, class_id, "A-1", "Asha", phone)
    password = (await client.post(f"{API}/students/{asha['id']}/parent-login", json={}, headers=admin)).json()["password"]
    parent, _ = await _parent_headers(client, phone, password)
    return class_id, admin, asha, parent


async def test_parent_reports_offline_payment_and_office_confirms(db, client):
    class_id, admin, asha, parent = await _family(client, "OFF1", "9848022360")
    await client.post(f"{API}/fees/items", json={**FEE, "name": "Term 1", "amount": "5000", "class_ids": [class_id]}, headers=admin)
    await client.put(f"{API}/fees/offline-instructions", json={"text": "UPI: school@okaxis"}, headers=admin)
    overview = (await client.get(f"{API}/me/parent/children/{asha['id']}", headers=parent)).json()
    assert overview["offline_instructions"] == "UPI: school@okaxis" and overview["offline_payments"] == []
    line = overview["fees"]["lines"][0]
    url = f"{API}/me/parent/children/{asha['id']}/fees/{line['id']}/offline"
    today = today_ist().isoformat()

    # UPI needs a transaction number or a screenshot; more than is due is refused.
    assert (await client.post(url, data={"amount": "5000", "method": "upi", "paid_on": today}, headers=parent)).json()["error"]["code"] == "reference_required"
    assert (await client.post(url, data={"amount": "6000", "method": "cash", "paid_on": today}, headers=parent)).status_code == 400
    assert (await client.post(url, data={"amount": "10", "method": "bitcoin", "paid_on": today}, headers=parent)).status_code == 422
    future = (today_ist() + timedelta(days=2)).isoformat()
    assert (await client.post(url, data={"amount": "10", "method": "cash", "paid_on": future}, headers=parent)).status_code == 400

    sent = await client.post(
        url, data={"amount": "3000", "method": "upi", "paid_on": today, "reference": "UTR123"},
        files={"proof": ("upi.png", PNG, "image/png")}, headers=parent,
    )
    assert sent.status_code == 201, sent.text
    claim = sent.json()
    assert (claim["status"], claim["has_proof"], claim["method_label"]) == ("submitted", True, "UPI")
    # A second report can't add up to more than the balance while the first waits.
    assert (await client.post(url, data={"amount": "2500", "method": "cash", "paid_on": today}, headers=parent)).status_code == 400
    cash = (await client.post(url, data={"amount": "2000", "method": "cash", "paid_on": today}, headers=parent)).json()

    # Nothing is counted until the office confirms.
    assert (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()["balance"] == 5000.0
    waiting = (await client.get(f"{API}/fees/claims", params={"status_filter": "submitted"}, headers=admin)).json()
    assert sorted(c["amount"] for c in waiting) == [2000.0, 3000.0]
    assert (await client.get(f"{API}/fees/claims/{claim['id']}/proof", headers=admin)).content == PNG

    approved = (await client.post(f"{API}/fees/claims/{claim['id']}/approve", headers=admin)).json()
    assert approved["status"] == "approved" and approved["receipt_number"].startswith("RCPT-")
    assert (await client.post(f"{API}/fees/claims/{claim['id']}/approve", headers=admin)).status_code == 409
    rejected = (await client.post(f"{API}/fees/claims/{cash['id']}/reject", json={"note": "Not in the cash book"}, headers=admin)).json()
    assert rejected["status"] == "rejected"

    account = (await client.get(f"{API}/fees/students/{asha['id']}", headers=admin)).json()
    assert account["balance"] == 2000.0
    payment = account["lines"][0]["payments"][0]
    assert (payment["method"], payment["reference"], payment["amount"]) == ("upi", "UTR123", 3000.0)
    mine = (await client.get(f"{API}/me/parent/children/{asha['id']}", headers=parent)).json()["offline_payments"]
    assert {c["status"] for c in mine} == {"approved", "rejected"}
    log = [e["summary"] for e in (await client.get(f"{API}/audit-log", params={"area": "fees"}, headers=admin)).json()]
    assert any("Confirmed ₹3000 paid by UPI" in s for s in log)

    # Another family can't report on this child, nor see the office's list.
    _, _, _, other = await _family(client, "OFF2", "9848022361")
    assert (await client.post(url, data={"amount": "10", "method": "cash", "paid_on": today}, headers=other)).status_code == 404
    assert (await client.get(f"{API}/fees/claims", headers=other)).status_code == 403


async def test_parent_uploads_documents_and_applies_leave(db, client):
    class_id, admin, asha, parent = await _family(client, "PX1", "9848022362")
    base = f"{API}/me/parent/children/{asha['id']}"

    assert (await client.put(f"{base}/photo", files={"file": ("a.png", PNG, "image/png")}, headers=parent)).status_code == 204
    assert (await client.get(f"{API}/students/{asha['id']}", headers=admin)).json()["has_photo"] is True
    doc = await client.post(f"{base}/documents", data={"doc_type": "birth_certificate"}, files={"file": ("b.pdf", PDF, "application/pdf")}, headers=parent)
    assert doc.status_code == 201 and doc.json()["status"] == "pending"
    assert (await client.get(f"{base}/documents/{doc.json()['id']}/file", headers=parent)).content == PDF
    staff_view = (await client.get(f"{API}/students/{asha['id']}/documents", headers=admin)).json()
    assert [d["status"] for d in staff_view] == ["pending"]

    start = today_ist() + timedelta(days=1)
    body = {"student_id": asha["id"], "leave_type": "sick", "from_date": start.isoformat(), "to_date": start.isoformat(), "reason": "Fever"}
    applied = await client.post(f"{API}/leave", json=body, headers=parent)
    assert applied.status_code == 201, applied.text
    leave = applied.json()
    assert (leave["applicant_name"], leave["applied_by_parent"], leave["student_id"]) == ("Asha", True, asha["id"])
    assert (await client.post(f"{API}/leave", json=body, headers=parent)).json()["error"]["code"] == "leave_overlaps"
    assert [lv["id"] for lv in (await client.get(f"{API}/leave/mine", headers=parent)).json()] == [leave["id"]]
    inbox = (await client.get(f"{API}/leave/inbox", headers=admin)).json()
    assert [(lv["applicant_name"], lv["can_review"]) for lv in inbox] == [("Asha", True)]
    assert (await client.post(f"{API}/leave/{leave['id']}/review", json={"status": "approved"}, headers=admin)).json()["status"] == "approved"

    # Not someone else's child.
    other_class, other_admin = await _school(client, "PX2")
    stranger = await _student(client, other_admin, other_class, "B-1", "Stranger")
    assert (await client.post(f"{API}/leave", json={**body, "student_id": stranger["id"]}, headers=parent)).status_code == 404
    assert (await client.get(f"{API}/me/parent/children/{stranger['id']}/documents", headers=parent)).status_code == 404
