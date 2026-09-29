"""Admissions.

Parents apply online from the school's public "apply" page (no login), or the
office records a walk-in enquiry. Admins get a bell notification, review the
application and its documents, and either approve it (which creates the
student with their parents and moves the documents into the student's
verified documents) or reject it with a reason. Approving also gives the
parent a login.

A school can charge an application fee. Parents pay it online right after
applying (with the school's own payment gateway account) or at the office, where the
admin marks it paid or waives it.
"""

import secrets
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Literal

import aiomysql
from fastapi import UploadFile, status
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.api.deps import CurrentUser
from app.core.errors import AppError
from app.core.modules import school_modules
from app.core.phone import normalize_indian_mobile
from app.db.database import db
from app.db.helpers import execute, fetch_all, fetch_one
from app.integrations import cashfree, gateways
from app.modules.alerts.service import today_ist
from app.modules.audit import service as audit
from app.modules.notifications import service as notifications
from app.modules.parents import service as parents
from app.modules.parents.service import ParentLoginOut
from app.modules.students import service as students
from app.modules.students.files import DOCUMENT_TYPES, MAX_DOCUMENT_BYTES, PHOTO_TYPES, private_path, save_private_file
from app.modules.students.schemas import CreateStudentRequest, GuardianIn

DocType = Literal["birth_certificate", "photo", "transfer_certificate", "marks_memo", "aadhaar", "other"]
DOC_LABELS = {
    "birth_certificate": "Birth certificate", "photo": "Photo", "transfer_certificate": "Transfer certificate (TC)",
    "marks_memo": "Marks memo", "aadhaar": "Aadhaar", "other": "Other",
}
MAX_DOCUMENTS = 5
MAX_ADMISSION_FEE = 100000
UPLOAD_WINDOW_MINUTES = 120


def _strip(value):
    return value.strip() if isinstance(value, str) else value


class ApplicationIn(BaseModel):
    student_name: str = Field(min_length=2, max_length=200)
    date_of_birth: date | None = None
    gender: Literal["male", "female", "other", ""] = ""
    class_applied: str = Field(min_length=1, max_length=50)
    previous_school: str = Field(default="", max_length=200)
    address: str = Field(default="", max_length=500)
    father_name: str = Field(default="", max_length=200)
    father_phone: str = Field(default="", max_length=20)
    mother_name: str = Field(default="", max_length=200)
    mother_phone: str = Field(default="", max_length=20)
    email: EmailStr | Literal[""] = ""
    message: str = Field(default="", max_length=1000)
    website: str = ""  # hidden trap field: people leave it empty, form-filling bots don't

    _strip_text = field_validator(
        "student_name", "class_applied", "previous_school", "address", "father_name", "father_phone",
        "mother_name", "mother_phone", "message", mode="before",
    )(_strip)

    @model_validator(mode="after")
    def _check(self):
        if not (self.father_name or self.mother_name):
            raise ValueError("Give the father's or mother's name.")
        phones = [p for p in (self.father_phone, self.mother_phone) if p]
        if not phones:
            raise ValueError("Give at least one parent's mobile number.")
        for phone in phones:
            if normalize_indian_mobile(phone) is None:
                raise ValueError(f"{phone} is not a valid 10-digit mobile number.")
        if self.date_of_birth and not (date(1990, 1, 1) <= self.date_of_birth <= date.today()):
            raise ValueError("Check the date of birth.")
        return self


class PublicForm(BaseModel):
    school_name: str
    school_code: str
    logo_url: str | None
    open: bool
    classes: list[str]
    admission_fee: float = 0
    online_payment: bool = False  # the fee can be paid online (the school connected Cashfree)


class Submitted(BaseModel):
    id: str
    application_no: str
    upload_token: str  # lets the parent attach documents for a short while, and pay the fee, without a login
    fee_amount: float = 0


class DocumentOut(BaseModel):
    id: str
    doc_type: str
    doc_type_label: str
    original_name: str
    content_type: str
    size_bytes: int


class ApplicationOut(BaseModel):
    id: str
    application_no: str
    source: str
    student_name: str
    date_of_birth: date | None
    gender: str
    class_applied: str
    previous_school: str
    address: str
    father_name: str
    father_phone: str
    mother_name: str
    mother_phone: str
    email: str
    message: str
    status: str
    review_note: str
    reviewed_by_name: str | None
    student_id: str | None
    created_at: str
    documents: list[DocumentOut]
    fee_amount: float = 0
    fee_status: str = "none"  # none, pending, paid, waived
    fee_method: str = ""  # online or office, once paid
    fee_payment_ref: str = ""
    # Only in the approve response: the parent login made (or linked) for the new student.
    parent_login: ParentLoginOut | None = None
    parent_login_note: str = ""


class ApproveIn(BaseModel):
    class_id: str
    admission_number: str | None = Field(default=None, max_length=50)  # blank: the next number
    admission_date: date | None = None

    _strip_text = field_validator("admission_number", mode="before")(_strip)


class RejectIn(BaseModel):
    note: str = Field(min_length=3, max_length=300)


class AdmissionSettings(BaseModel):
    open: bool
    admission_fee: float | None = Field(default=None, ge=0, le=MAX_ADMISSION_FEE)  # rupees; omit to keep the saved fee


class FeeTokenIn(BaseModel):
    token: str = Field(min_length=1, max_length=64)


class FeeOrderOut(BaseModel):
    order_id: str
    provider: str = "cashfree"  # which checkout to open: "cashfree", "razorpay" or "phonepe"
    payment_session_id: str = ""  # Cashfree Checkout
    key_id: str = ""  # Razorpay Checkout
    gateway_order_id: str = ""  # Razorpay's order id
    checkout_url: str = ""  # PhonePe checkout page
    environment: str
    amount: float
    school_name: str


class FeeStatusOut(BaseModel):
    fee_status: str
    fee_amount: float


class FeeDecisionIn(BaseModel):
    action: Literal["paid", "waived"]
    reference: str = Field(default="", max_length=100)  # e.g. the office receipt number

    _strip_text = field_validator("reference", mode="before")(_strip)


# --- Public side -------------------------------------------------------------------------


async def _public_school(code: str) -> dict:
    school = await fetch_one(
        "SELECT * FROM schools WHERE (code = %s OR subdomain = %s) AND status = 'active' AND billing_status <> 'suspended'",
        (code.upper(), code.lower()),
    )
    if school is None or "admissions" not in await school_modules(school["id"]):
        raise AppError(status.HTTP_404_NOT_FOUND, "school_not_found", "School not found.")
    return school


async def is_open(school_id: str) -> bool:
    row = await fetch_one("SELECT admissions_open FROM school_settings WHERE school_id = %s", (school_id,))
    return bool(row["admissions_open"]) if row else True


async def admission_fee(school_id: str) -> Decimal:
    row = await fetch_one("SELECT admission_fee FROM school_settings WHERE school_id = %s", (school_id,))
    return Decimal(row["admission_fee"]) if row else Decimal("0")


async def get_settings(school_id: str) -> AdmissionSettings:
    return AdmissionSettings(open=await is_open(school_id), admission_fee=float(await admission_fee(school_id)))


async def _class_names(school_id: str) -> list[str]:
    rows = await fetch_all("SELECT DISTINCT name FROM classes WHERE school_id = %s AND is_archived = 0", (school_id,))
    return sorted((r["name"] for r in rows), key=_class_order)


def _class_order(name: str):
    # Nursery, LKG, UKG first, then numbered classes in number order.
    lowered = name.lower()
    for position, word in enumerate(("nursery", "pre", "lkg", "ukg")):
        if word in lowered:
            return (0, position, name)
    digits = "".join(ch for ch in name if ch.isdigit())
    return (1, int(digits) if digits else 999, name)


async def public_form(code: str) -> PublicForm:
    school = await _public_school(code)
    site = await fetch_one("SELECT logo_url FROM school_sites WHERE school_id = %s", (school["id"],))
    return PublicForm(
        school_name=school["name"], school_code=school["code"], logo_url=site["logo_url"] if site else None,
        open=await is_open(school["id"]), classes=await _class_names(school["id"]),
        admission_fee=float(await admission_fee(school["id"])),
        online_payment=await parents.online_settings(school["id"]) is not None,
    )


async def _next_number(cur, school_id: str, kind: str, year: int) -> int:
    # LAST_INSERT_ID(expr) is per-connection, so concurrent requests never share a number.
    await cur.execute(
        """
        INSERT INTO admission_counters (school_id, kind, year, last_number) VALUES (%s, %s, %s, LAST_INSERT_ID(1))
        ON DUPLICATE KEY UPDATE last_number = LAST_INSERT_ID(last_number + 1)
        """,
        (school_id, kind, year),
    )
    await cur.execute("SELECT LAST_INSERT_ID() AS n")
    return (await cur.fetchone())["n"]


def _ten_digits(phone: str) -> str:
    """Stored like other guardian phones: the 10-digit mobile without +91."""
    normalized = normalize_indian_mobile(phone) if phone else None
    return normalized[-10:] if normalized else ""


async def _insert(school_id: str, payload: ApplicationIn, source: str) -> Submitted:
    if payload.class_applied not in await _class_names(school_id):
        raise AppError(status.HTTP_400_BAD_REQUEST, "unknown_class", "Choose a class from the list.")
    application_id, token = str(uuid.uuid4()), secrets.token_hex(32)
    fee = await admission_fee(school_id)
    year = today_ist().year
    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                application_no = f"APP/{year}/{await _next_number(cur, school_id, 'application', year):04d}"
                await cur.execute(
                    """
                    INSERT INTO admission_applications (id, school_id, application_no, source, student_name, date_of_birth, gender,
                        class_applied, previous_school, address, father_name, father_phone, mother_name, mother_phone, email, message, upload_token,
                        fee_amount, fee_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        application_id, school_id, application_no, source, payload.student_name, payload.date_of_birth, payload.gender,
                        payload.class_applied, payload.previous_school, payload.address, payload.father_name,
                        _ten_digits(payload.father_phone), payload.mother_name,
                        _ten_digits(payload.mother_phone), payload.email, payload.message, token,
                        fee, "pending" if fee > 0 else "none",
                    ),
                )
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()
    return Submitted(id=application_id, application_no=application_no, upload_token=token, fee_amount=float(fee))


async def submit_online(code: str, payload: ApplicationIn) -> Submitted:
    school = await _public_school(code)
    if not await is_open(school["id"]):
        raise AppError(status.HTTP_409_CONFLICT, "admissions_closed", "Admissions are closed right now. Please contact the school.")
    if payload.website:
        raise AppError(status.HTTP_400_BAD_REQUEST, "invalid_form", "Please try again.")
    submitted = await _insert(school["id"], payload, "online")
    await notifications.notify(
        await notifications.admin_user_ids(school["id"]),
        school_id=school["id"],
        title=f"New admission application: {payload.student_name}",
        body=f"{payload.class_applied} · {submitted.application_no}",
        link="admissions",
    )
    return submitted


async def _save_document(application: dict, doc_type: str, file: UploadFile) -> None:
    count = await fetch_one("SELECT COUNT(*) AS n FROM admission_documents WHERE application_id = %s", (application["id"],))
    if count["n"] >= MAX_DOCUMENTS:
        raise AppError(status.HTTP_400_BAD_REQUEST, "too_many_documents", f"At most {MAX_DOCUMENTS} documents per application.")
    allowed = PHOTO_TYPES if doc_type == "photo" else DOCUMENT_TYPES
    path, size = await save_private_file(
        folder=Path(application["school_id"]) / "admissions" / application["id"], file=file, allowed_types=allowed, max_bytes=MAX_DOCUMENT_BYTES
    )
    await execute(
        """
        INSERT INTO admission_documents (id, application_id, doc_type, file_path, content_type, size_bytes, original_name)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (str(uuid.uuid4()), application["id"], doc_type, path, file.content_type, size, (file.filename or "")[:255]),
    )


async def upload_with_token(application_id: str, token: str, doc_type: str, file: UploadFile) -> None:
    # The age is worked out in the database, so the server's time zone doesn't matter.
    application = await fetch_one(
        "SELECT *, TIMESTAMPDIFF(MINUTE, created_at, CURRENT_TIMESTAMP(6)) AS age_minutes FROM admission_applications WHERE id = %s",
        (application_id,),
    )
    if (
        application is None
        or not application["upload_token"]
        or not secrets.compare_digest(application["upload_token"], token)
        or application["status"] != "new"
        or application["age_minutes"] > UPLOAD_WINDOW_MINUTES
    ):
        raise AppError(status.HTTP_403_FORBIDDEN, "upload_not_allowed", "Documents can't be added to this application any more. Bring them to the school office.")
    await _save_document(application, doc_type, file)


# --- Application fee, paid online by the parent -------------------------------------------


async def _fee_application(code: str, application_id: str, token: str) -> tuple[dict, dict, dict]:
    """The school, application and payment gateway settings, after checking the parent's token.

    The token works until the application is decided (not only for the upload window),
    so a parent can come back to pay from the same page.
    """
    school = await _public_school(code)
    application = await fetch_one("SELECT * FROM admission_applications WHERE id = %s AND school_id = %s", (application_id, school["id"]))
    if application is None or not application["upload_token"] or not secrets.compare_digest(application["upload_token"], token):
        raise AppError(status.HTTP_403_FORBIDDEN, "payment_not_allowed", "This application can't be paid for here. Please pay at the school office.")
    settings = await parents.online_settings(school["id"])
    if settings is None:
        raise AppError(status.HTTP_409_CONFLICT, "online_payment_unavailable", "Online payment isn't available. Please pay the fee at the school office.")
    return school, application, settings


async def start_fee_payment(code: str, application_id: str, token: str) -> FeeOrderOut:
    school, application, settings = await _fee_application(code, application_id, token)
    if application["status"] != "new" or application["fee_status"] != "pending":
        raise AppError(status.HTTP_409_CONFLICT, "fee_not_due", "No application fee is due.")
    # A new order for each try; gateway order ids are at most 40 characters (Razorpay).
    order_id = f"adm_{uuid.uuid4().hex}"
    try:
        checkout = await gateways.create_order(
            settings, parents.secret_of(settings), order_id=order_id, amount=Decimal(application["fee_amount"]),
            customer_id=application["id"].replace("-", ""), customer_phone=application["father_phone"] or application["mother_phone"],
            customer_name=application["father_name"] or application["mother_name"],
            note=f"Application fee — {application['student_name']} ({application['application_no']})", redirect_url=parents.return_url(),
        )
    except gateways.GatewayError as exc:
        raise parents.gateway_failed(exc) from exc
    await execute(
        "UPDATE admission_applications SET fee_order_id = %s, fee_gateway = %s, fee_gateway_ref = %s WHERE id = %s",
        (order_id, checkout.provider, checkout.gateway_ref, application_id),
    )
    return FeeOrderOut(
        order_id=order_id, provider=checkout.provider, payment_session_id=checkout.payment_session_id, key_id=checkout.key_id,
        gateway_order_id=checkout.gateway_ref if checkout.provider in ("razorpay", "demo") else "", checkout_url=checkout.checkout_url,
        environment=checkout.environment, amount=float(application["fee_amount"]), school_name=school["name"],
    )


async def _finalize_fee(application_id: str, settings: dict) -> str:
    """Asks the gateway about the application's latest order and records it if paid. Returns the fee status."""
    application = await fetch_one("SELECT * FROM admission_applications WHERE id = %s", (application_id,))
    if application["fee_status"] != "pending" or not application["fee_order_id"]:
        return application["fee_status"]
    order_id = application["fee_order_id"]
    if (application["fee_gateway"] or "cashfree") != settings["provider"]:
        return "pending"  # the school switched gateways since; the old one can't be asked
    try:
        state = await gateways.check_order(settings, parents.secret_of(settings), application["fee_gateway_ref"] or order_id)
    except gateways.GatewayError as exc:
        raise parents.gateway_failed(exc) from exc
    if state.status != "paid" or state.amount != Decimal(application["fee_amount"]):
        return "pending"  # not paid, or not the fee's amount: not counted
    # Only a pending row with this order is updated, so the confirm call and the webhook can't both record it.
    await execute(
        """
        UPDATE admission_applications SET fee_status = 'paid', fee_method = 'online', fee_payment_ref = %s, fee_paid_at = %s
        WHERE id = %s AND fee_status = 'pending' AND fee_order_id = %s
        """,
        (state.payment_ref or order_id, datetime.now(timezone.utc), application_id, order_id),
    )
    return "paid"


async def confirm_fee_payment(code: str, application_id: str, token: str) -> FeeStatusOut:
    _, application, settings = await _fee_application(code, application_id, token)
    fee_status = await _finalize_fee(application_id, settings)
    if fee_status == "pending":
        raise AppError(status.HTTP_409_CONFLICT, "payment_pending", parents.pending_message(settings, "the school will see it"))
    return FeeStatusOut(fee_status=fee_status, fee_amount=float(application["fee_amount"]))


async def handle_fee_webhook(provider: str, order_ref: str, raw_body: bytes, timestamp: str, signature: str) -> None:
    """A gateway's webhook for an application-fee order (does nothing for an order that isn't one)."""
    application = await fetch_one(
        "SELECT id, school_id, fee_status FROM admission_applications WHERE fee_gateway_ref = %s AND fee_gateway = %s", (order_ref, provider)
    )
    if application is None:
        return
    settings = await parents.online_settings(application["school_id"])
    if settings is None or settings["provider"] != provider:
        return
    if provider == "cashfree" and not cashfree.verify_webhook_signature(raw_body, timestamp, signature, parents.secret_of(settings)):
        raise AppError(status.HTTP_401_UNAUTHORIZED, "invalid_signature", "Webhook signature doesn't match.")
    if application["fee_status"] == "pending":
        await _finalize_fee(application["id"], settings)


# --- Admin side ------------------------------------------------------------------------------


def _document_out(r: dict) -> DocumentOut:
    return DocumentOut(
        id=r["id"], doc_type=r["doc_type"], doc_type_label=DOC_LABELS.get(r["doc_type"], r["doc_type"]),
        original_name=r["original_name"], content_type=r["content_type"], size_bytes=r["size_bytes"],
    )


def _out(r: dict, documents: list[dict]) -> ApplicationOut:
    return ApplicationOut(
        id=r["id"], application_no=r["application_no"], source=r["source"], student_name=r["student_name"],
        date_of_birth=r["date_of_birth"], gender=r["gender"], class_applied=r["class_applied"], previous_school=r["previous_school"],
        address=r["address"], father_name=r["father_name"], father_phone=r["father_phone"], mother_name=r["mother_name"],
        mother_phone=r["mother_phone"], email=r["email"], message=r["message"], status=r["status"], review_note=r["review_note"],
        reviewed_by_name=r.get("reviewed_by_name"), student_id=r["student_id"], created_at=r["created_at"].isoformat(),
        documents=[_document_out(d) for d in documents],
        fee_amount=float(r["fee_amount"]), fee_status=r["fee_status"], fee_method=r["fee_method"], fee_payment_ref=r["fee_payment_ref"],
    )


_SELECT = "SELECT a.*, u.full_name AS reviewed_by_name FROM admission_applications a LEFT JOIN users u ON u.id = a.reviewed_by"


async def list_applications(user: CurrentUser, *, status_filter: str | None) -> list[ApplicationOut]:
    where, params = ["a.school_id = %s"], [user.school_id]
    if status_filter:
        where.append("a.status = %s")
        params.append(status_filter)
    rows = await fetch_all(f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY a.created_at DESC LIMIT 500", tuple(params))
    documents: dict[str, list[dict]] = {}
    if rows:
        placeholders = ", ".join(["%s"] * len(rows))
        for d in await fetch_all(f"SELECT * FROM admission_documents WHERE application_id IN ({placeholders}) ORDER BY created_at", tuple(r["id"] for r in rows)):
            documents.setdefault(d["application_id"], []).append(d)
    return [_out(r, documents.get(r["id"], [])) for r in rows]


async def _row(user: CurrentUser, application_id: str) -> dict:
    row = await fetch_one(f"{_SELECT} WHERE a.id = %s AND a.school_id = %s", (application_id, user.school_id))
    if row is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "application_not_found", "Application not found.")
    return row


async def get_application(user: CurrentUser, application_id: str) -> ApplicationOut:
    row = await _row(user, application_id)
    documents = await fetch_all("SELECT * FROM admission_documents WHERE application_id = %s ORDER BY created_at", (application_id,))
    return _out(row, documents)


async def create_walk_in(user: CurrentUser, payload: ApplicationIn) -> ApplicationOut:
    submitted = await _insert(user.school_id, payload, "office")
    return await get_application(user, submitted.id)


async def add_document(user: CurrentUser, application_id: str, doc_type: str, file: UploadFile) -> ApplicationOut:
    row = await _row(user, application_id)
    if row["status"] != "new":
        raise AppError(status.HTTP_409_CONFLICT, "already_decided", "This application was already decided.")
    await _save_document(row, doc_type, file)
    return await get_application(user, application_id)


async def document_file(user: CurrentUser, application_id: str, document_id: str) -> tuple[Path, str, str]:
    await _row(user, application_id)
    doc = await fetch_one("SELECT * FROM admission_documents WHERE id = %s AND application_id = %s", (document_id, application_id))
    if doc is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "file_not_found", "File not found.")
    return private_path(doc["file_path"]), doc["content_type"], doc["original_name"]


async def suggest_admission_number(user: CurrentUser) -> str:
    """The next number in the school's sequence, e.g. 20260007; not reserved until a student is approved."""
    year = today_ist().year
    row = await fetch_one("SELECT last_number FROM admission_counters WHERE school_id = %s AND kind = 'admission' AND year = %s", (user.school_id, year))
    number = (row["last_number"] if row else 0) + 1
    while await fetch_one("SELECT id FROM students WHERE school_id = %s AND admission_number = %s", (user.school_id, f"{year}{number:04d}")):
        number += 1
    return f"{year}{number:04d}"


def _student_payload(app: dict, payload: ApproveIn, admission_number: str) -> CreateStudentRequest:
    father = GuardianIn(full_name=app["father_name"], phone=app["father_phone"], email=app["email"]) if app["father_name"] else None
    mother = GuardianIn(full_name=app["mother_name"], phone=app["mother_phone"], email="" if father else app["email"]) if app["mother_name"] else None
    # The primary contact is whoever gave a mobile number, the father first.
    primary = "father" if father and app["father_phone"] else "mother" if mother and app["mother_phone"] else ("father" if father else "mother")
    return CreateStudentRequest(
        admission_number=admission_number, full_name=app["student_name"], class_id=payload.class_id,
        date_of_birth=app["date_of_birth"], gender=app["gender"], admission_date=payload.admission_date or today_ist(),
        address=app["address"], father=father, mother=mother, primary_contact=primary,
    )


async def approve(user: CurrentUser, application_id: str, payload: ApproveIn) -> ApplicationOut:
    app = await _row(user, application_id)
    if app["status"] != "new":
        raise AppError(status.HTTP_409_CONFLICT, "already_decided", "This application was already decided.")
    cls = await fetch_one("SELECT id FROM classes WHERE id = %s AND school_id = %s AND is_archived = 0", (payload.class_id, user.school_id))
    if cls is None:
        raise AppError(status.HTTP_404_NOT_FOUND, "class_not_found", "Class not found.")
    documents = await fetch_all("SELECT * FROM admission_documents WHERE application_id = %s", (application_id,))
    year = today_ist().year
    now = datetime.now(timezone.utc)

    async with db.pool.acquire() as conn:
        await conn.begin()
        try:
            async with conn.cursor() as cur:
                admission_number = payload.admission_number
                if not admission_number:
                    # Take numbers from the school's sequence, skipping any already used by hand.
                    while True:
                        admission_number = f"{year}{await _next_number(cur, user.school_id, 'admission', year):04d}"
                        await cur.execute("SELECT id FROM students WHERE school_id = %s AND admission_number = %s", (user.school_id, admission_number))
                        if await cur.fetchone() is None:
                            break
                student_id = await students.insert_student(cur, user.school_id, _student_payload(app, payload, admission_number))
                for doc in documents:
                    if doc["doc_type"] == "photo":
                        await cur.execute("UPDATE students SET photo_path = %s WHERE id = %s", (doc["file_path"], student_id))
                        continue
                    await cur.execute(
                        """
                        INSERT INTO student_documents (id, school_id, student_id, doc_type, title, file_path, content_type, size_bytes,
                                                       original_name, status, uploaded_by, reviewed_by, reviewed_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'approved', %s, %s, %s)
                        """,
                        (
                            str(uuid.uuid4()), user.school_id, student_id, doc["doc_type"],
                            f"From admission {app['application_no']}", doc["file_path"], doc["content_type"], doc["size_bytes"],
                            doc["original_name"], user.id, user.id, now,
                        ),
                    )
                await cur.execute(
                    """
                    UPDATE admission_applications SET status = 'approved', student_id = %s, reviewed_by = %s, reviewed_at = %s, upload_token = NULL
                    WHERE id = %s
                    """,
                    (student_id, user.id, now, application_id),
                )
                admitted_as = admission_number
        except aiomysql.IntegrityError as exc:
            await conn.rollback()
            raise AppError(status.HTTP_409_CONFLICT, "admission_number_taken", "Another student already has this admission number.") from exc
        except Exception:
            await conn.rollback()
            raise
        await conn.commit()
    await audit.record(
        user, "admissions.approved", f"Admitted {app['student_name']} ({app['application_no']}) as {admitted_as}",
        entity_type="student", entity_id=student_id,
    )
    result = await get_application(user, application_id)
    # The parent gets a login straight away (or the new child joins their existing one).
    # A problem here doesn't undo the admission; the admin can retry from the student's page.
    student = await fetch_one("SELECT * FROM students WHERE id = %s", (student_id,))
    try:
        result.parent_login = await parents.link_parent(student)
    except AppError as exc:
        result.parent_login_note = f"No parent login was made: {exc.detail}"
    return result


async def reject(user: CurrentUser, application_id: str, payload: RejectIn) -> ApplicationOut:
    app = await _row(user, application_id)
    if app["status"] != "new":
        raise AppError(status.HTTP_409_CONFLICT, "already_decided", "This application was already decided.")
    await execute(
        "UPDATE admission_applications SET status = 'rejected', review_note = %s, reviewed_by = %s, reviewed_at = %s, upload_token = NULL WHERE id = %s",
        (payload.note.strip(), user.id, datetime.now(timezone.utc), application_id),
    )
    await audit.record(
        user, "admissions.rejected", f"Rejected {app['student_name']}'s application {app['application_no']}: {payload.note.strip()}",
        entity_type="admission", entity_id=application_id,
    )
    return await get_application(user, application_id)


async def record_fee(user: CurrentUser, application_id: str, payload: FeeDecisionIn) -> ApplicationOut:
    """The office took the application fee in person, or waived it."""
    app = await _row(user, application_id)
    if app["fee_status"] != "pending":
        raise AppError(status.HTTP_409_CONFLICT, "fee_not_due", "No application fee is due on this application.")
    paid = payload.action == "paid"
    await execute(
        """
        UPDATE admission_applications SET fee_status = %s, fee_method = %s, fee_payment_ref = %s, fee_paid_at = %s
        WHERE id = %s AND fee_status = 'pending'
        """,
        (payload.action, "office" if paid else "", payload.reference, datetime.now(timezone.utc) if paid else None, application_id),
    )
    what = f"Application fee ₹{Decimal(app['fee_amount']):,.2f} for {app['student_name']} ({app['application_no']})"
    how = (f"received at the office, ref {payload.reference}" if payload.reference else "received at the office") if paid else "waived"
    await audit.record(user, f"admissions.fee_{payload.action}", f"{what} {how}", entity_type="admission", entity_id=application_id)
    return await get_application(user, application_id)


async def save_settings(user: CurrentUser, payload: AdmissionSettings) -> AdmissionSettings:
    fee = round(Decimal(str(payload.admission_fee)), 2) if payload.admission_fee is not None else await admission_fee(user.school_id)
    await execute(
        """
        INSERT INTO school_settings (school_id, admissions_open, admission_fee) VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE admissions_open = VALUES(admissions_open), admission_fee = VALUES(admission_fee)
        """,
        (user.school_id, payload.open, fee),
    )
    return await get_settings(user.school_id)
