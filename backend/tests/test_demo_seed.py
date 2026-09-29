from datetime import date

from scripts.demo_seed import ADMIN_EMAIL, seed_demo_school

PASSWORD = "DemoPass!2026"
TODAY = date(2026, 9, 25)  # a Friday


async def _count(conn, sql, params=()):
    async with conn.cursor() as cur:
        await cur.execute(sql, params)
        row = await cur.fetchone()
    return next(iter(row.values()))


async def test_demo_school_is_seeded_once(db):
    async with db.pool.acquire() as conn:
        assert await seed_demo_school(conn, PASSWORD, TODAY) is True
        assert await seed_demo_school(conn, PASSWORD, TODAY) is False

        assert await _count(conn, "SELECT COUNT(*) FROM classes") == 6
        assert await _count(conn, "SELECT COUNT(*) FROM teachers") == 6
        assert await _count(conn, "SELECT COUNT(*) FROM subjects") == 6
        assert await _count(conn, "SELECT COUNT(*) FROM class_subjects") == 6 * 6
        assert await _count(conn, "SELECT COUNT(*) FROM students") == 120
        assert await _count(conn, "SELECT COUNT(*) FROM student_guardians") == 240
        assert await _count(conn, "SELECT COUNT(*) FROM students WHERE date_of_birth IS NULL OR gender = ''") == 0
        assert await _count(conn, "SELECT COUNT(*) FROM attendance") == 120 * 30
        assert await _count(conn, "SELECT COUNT(*) FROM staff_attendance") == 6 * 30
        assert await _count(conn, "SELECT COUNT(*) FROM staff_attendance WHERE status = 'absent'") == 0
        # Only weekdays, ending on the given day.
        assert await _count(conn, "SELECT COUNT(*) FROM attendance WHERE WEEKDAY(attendance_date) >= 5") == 0
        assert await _count(conn, "SELECT COUNT(*) FROM attendance WHERE attendance_date > %s", (TODAY,)) == 0


async def test_demo_teacher_sees_only_their_class_with_attendance(db, client):
    async with db.pool.acquire() as conn:
        await seed_demo_school(conn, PASSWORD, TODAY)

    login = await client.post("/api/v1/auth/login", json={"email": "demo-teacher1@example.com", "password": PASSWORD})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    classes = (await client.get("/api/v1/classes", headers=headers)).json()
    assert [c["name"] for c in classes] == ["Grade 1"]

    response = await client.get(
        f"/api/v1/classes/{classes[0]['id']}/attendance", params={"date": TODAY.isoformat()}, headers=headers
    )
    assert response.status_code == 200


async def test_demo_admin_can_log_in(db, client):
    async with db.pool.acquire() as conn:
        await seed_demo_school(conn, PASSWORD, TODAY)

    response = await client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "admin"
