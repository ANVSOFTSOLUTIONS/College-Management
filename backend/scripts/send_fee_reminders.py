"""Send overdue-fee reminders (SMS / WhatsApp) to parents in every active college.

For a cPanel cron job, e.g. every Monday at 10:00:

    cd /home/<user>/college_backend && /home/<user>/virtualenv/college_backend/3.11/bin/python -m scripts.send_fee_reminders

A student gets at most one reminder per day, so running it twice is harmless.
Nothing is sent while SMS_ENABLED and WHATSAPP_ENABLED are off (alerts are
still logged as "not sent").
"""

import asyncio

from app.api.deps import CurrentUser
from app.db.database import close_mysql_connection, connect_to_mysql
from app.db.helpers import fetch_all
from app.modules.fees.service import send_reminders


async def main() -> None:
    await connect_to_mysql()
    try:
        schools = await fetch_all("SELECT id, name FROM schools WHERE status = 'active' AND billing_status <> 'suspended'")
        for school in schools:
            system = CurrentUser(id=None, school_id=school["id"], role="admin", email=None, full_name="Automatic reminder")
            result = await send_reminders(system, class_id=None, only_overdue=True)
            print(f"{school['name']}: {result.students_with_dues} students with overdue fees, {result.alerts_created} reminders")
    finally:
        await close_mysql_connection()


if __name__ == "__main__":
    asyncio.run(main())
