"""Inventory stock movements, gate passes with parent notifications, and the visitor register."""

from datetime import datetime, timedelta

from app.db.helpers import execute
from tests.factories import auth_headers, create_school, create_user, login

PASSWORD = "Secret123!"
API = "/api/v1"


async def _admin(client, code):
    school_id = await create_school(code=code)
    await create_user(school_id=school_id, email=f"{code}-admin@example.com".lower(), password=PASSWORD, role="admin")
    return auth_headers((await login(client, f"{code}-admin@example.com".lower(), PASSWORD)).json()["access_token"])


async def test_inventory_movements(db, client):
    admin = await _admin(client, "INV1")
    item = await client.post(f"{API}/inventory/items", json={"name": "Microscope", "category": "Lab", "location": "Biology lab", "quantity": 10, "min_quantity": 3},
                             headers=admin)
    assert item.status_code == 201, item.text
    item = item.json()
    assert (item["available"], item["low_stock"]) == (10, False)
    url = f"{API}/inventory/items/{item['id']}/movements"

    assert (await client.post(url, json={"kind": "issue", "quantity": 2}, headers=admin)).json()["error"]["code"] == "person_required"
    issued = (await client.post(url, json={"kind": "issue", "quantity": 4, "person": "Ravi (B.Sc lab)"}, headers=admin)).json()
    assert (issued["quantity"], issued["issued"], issued["available"]) == (10, 4, 6)
    assert (await client.post(url, json={"kind": "damaged", "quantity": 7}, headers=admin)).json()["error"]["code"] == "not_enough_stock"
    damaged = (await client.post(url, json={"kind": "damaged", "quantity": 6, "note": "Lens broken"}, headers=admin)).json()
    assert (damaged["quantity"], damaged["available"], damaged["low_stock"]) == (4, 0, False)
    back = (await client.post(url, json={"kind": "return", "quantity": 4}, headers=admin)).json()
    assert (back["issued"], back["available"]) == (0, 4)
    assert (await client.post(url, json={"kind": "return", "quantity": 1}, headers=admin)).json()["error"]["code"] == "not_issued"
    await client.post(url, json={"kind": "out", "quantity": 1}, headers=admin)
    assert [i["name"] for i in (await client.get(f"{API}/inventory/items", params={"low_only": True}, headers=admin)).json()] == ["Microscope"]
    history = (await client.get(url, headers=admin)).json()
    assert sorted(h["kind"] for h in history) == ["damaged", "in", "issue", "out", "return"]
    duplicate = await client.post(f"{API}/inventory/items", json={"name": "Microscope", "location": "Biology lab"}, headers=admin)
    assert duplicate.json()["error"]["code"] == "item_exists"


async def test_gate_pass_flow_and_visitors(db, client):
    admin = await _admin(client, "GAT1")
    teacher = (await client.post(f"{API}/teachers", json={"email": "gat1-f@example.com", "full_name": "Ravi", "password": PASSWORD}, headers=admin)).json()
    batch = (await client.post(f"{API}/classes", json={"name": "B.Sc", "section": "A", "academic_year": "2026", "class_teacher_id": teacher["id"]}, headers=admin)).json()
    asha = (await client.post(f"{API}/students", json={"admission_number": "S1", "full_name": "Asha", "class_id": batch["id"]}, headers=admin)).json()
    await client.post(f"{API}/students/{asha['id']}/login", json={"password": "StudentPass1"}, headers=admin)
    asha_h = auth_headers((await client.post(f"{API}/auth/login", json={"college_code": "GAT1", "roll_number": "S1", "password": "StudentPass1"})).json()["access_token"])

    now = datetime.now()
    body = {"reason": "Going home for the festival", "leave_at": (now + timedelta(hours=1)).isoformat(timespec="minutes"),
            "return_by": (now + timedelta(days=2)).isoformat(timespec="minutes")}
    url = f"{API}/me/parent/children/{asha['id']}/gate-passes"
    made = await client.post(url, json=body, headers=asha_h)
    assert made.status_code == 201, made.text
    assert made.json()[0]["status"] == "pending"
    assert (await client.post(url, json=body, headers=asha_h)).json()["error"]["code"] == "pass_open"
    assert (await client.post(url, json={**body, "return_by": body["leave_at"]}, headers=asha_h)).status_code == 422

    passes = (await client.get(f"{API}/gate/passes", headers=admin)).json()
    pass_id = passes[0]["id"]
    assert (await client.post(f"{API}/gate/passes/{pass_id}/out", headers=admin)).json()["error"]["code"] == "not_approved"
    approved = (await client.post(f"{API}/gate/passes/{pass_id}/decide", json={"approve": True}, headers=admin)).json()
    assert approved["status"] == "approved"
    out = (await client.post(f"{API}/gate/passes/{pass_id}/out", headers=admin)).json()
    assert (out["status"], out["went_out_at"] is not None, out["late"]) == ("out", True, False)

    # Overdue: pretend the return time passed.
    await execute("UPDATE gate_passes SET return_by = %s WHERE id = %s", (now - timedelta(hours=1), pass_id))
    back = (await client.post(f"{API}/gate/passes/{pass_id}/returned", headers=admin)).json()
    assert (back["status"], back["late"]) == ("returned", True)
    notes = [n["title"] for n in (await client.get(f"{API}/notifications", headers=asha_h)).json()["items"]]
    assert any("Gate pass approved" in t for t in notes) and any("left campus" in t for t in notes) and any("back on campus (late)" in t for t in notes)

    visitor = (await client.post(f"{API}/gate/visitors", json={"name": "Courier", "purpose": "Delivery", "to_meet": "Office"}, headers=admin)).json()
    assert [v["name"] for v in (await client.get(f"{API}/gate/visitors", params={"inside_only": True}, headers=admin)).json()] == ["Courier"]
    assert (await client.post(f"{API}/gate/visitors/{visitor['id']}/out", headers=admin)).json()["out_at"] is not None
    assert (await client.get(f"{API}/gate/visitors", params={"inside_only": True}, headers=admin)).json() == []
