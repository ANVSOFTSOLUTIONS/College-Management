from datetime import date

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, require_roles
from app.modules.audit import service as audit
from app.modules.payroll import service
from app.modules.payroll.service import PayIn, PayrollMonth, SalaryIn, SalaryOut, SlipAdjustIn, SlipOut

router = APIRouter(prefix="/payroll", tags=["payroll"])

_admin = require_roles("admin")
_staff = require_roles("admin", "teacher")


@router.get("/salaries", response_model=list[SalaryOut])
async def list_salaries(current_user: CurrentUser = Depends(_admin)) -> list[SalaryOut]:
    """Every active teacher, with their salary if set."""
    return await service.list_salaries(current_user)


@router.put("/salaries/{teacher_id}", response_model=SalaryOut)
async def save_salary(teacher_id: str, payload: SalaryIn, current_user: CurrentUser = Depends(_admin)) -> SalaryOut:
    salary = await service.save_salary(current_user, teacher_id, payload)
    await audit.record(
        current_user, "staff.salary",
        f"Set {salary.full_name}'s salary: basic ₹{payload.basic}, allowances ₹{payload.allowances}, deductions ₹{payload.deductions}",
        entity_type="teacher", entity_id=teacher_id,
    )
    return salary


@router.get("/months/{month}", response_model=PayrollMonth)
async def month_payroll(month: date, current_user: CurrentUser = Depends(_admin)) -> PayrollMonth:
    """Payslips for the month containing `month`, and teachers who still have no salary set."""
    return await service.month_payroll(current_user, month)


@router.post("/months/{month}/generate", response_model=PayrollMonth)
async def generate(month: date, current_user: CurrentUser = Depends(_admin)) -> PayrollMonth:
    """Creates or refreshes draft payslips from staff attendance and holidays; paid payslips are left alone."""
    return await service.generate(current_user, month)


@router.get("/slips/{slip_id}", response_model=SlipOut)
async def get_slip(slip_id: str, current_user: CurrentUser = Depends(_staff)) -> SlipOut:
    """A payslip for printing. Teachers can open only their own paid payslips."""
    return await service.get_slip(current_user, slip_id)


@router.patch("/slips/{slip_id}", response_model=SlipOut)
async def adjust(slip_id: str, payload: SlipAdjustIn, current_user: CurrentUser = Depends(_admin)) -> SlipOut:
    """Changes loss-of-pay days (and the note) on a draft payslip."""
    slip = await service.adjust(current_user, slip_id, payload)
    await audit.record(
        current_user, "staff.payslip_adjusted", f"Set {slip.full_name}'s loss-of-pay days for {slip.month} to {slip.lop_days:g} (net ₹{slip.net:g})",
        entity_type="payslip", entity_id=slip_id,
    )
    return slip


@router.post("/slips/{slip_id}/pay", response_model=SlipOut)
async def pay(slip_id: str, payload: PayIn, current_user: CurrentUser = Depends(_admin)) -> SlipOut:
    slip = await service.pay(current_user, slip_id, payload)
    await audit.record(
        current_user, "staff.payslip_paid", f"Paid {slip.full_name}'s salary for {slip.month}: ₹{slip.net:g} by {slip.payment_mode_label}",
        entity_type="payslip", entity_id=slip_id,
    )
    return slip


@router.post("/slips/{slip_id}/revert", response_model=SlipOut)
async def revert(slip_id: str, current_user: CurrentUser = Depends(_admin)) -> SlipOut:
    """Back to draft, e.g. to correct a payslip marked paid by mistake."""
    slip = await service.revert(current_user, slip_id)
    await audit.record(
        current_user, "staff.payslip_reverted", f"Reverted {slip.full_name}'s {slip.month} payslip to draft", entity_type="payslip", entity_id=slip_id
    )
    return slip


@router.get("/mine", response_model=list[SlipOut])
async def my_slips(current_user: CurrentUser = Depends(require_roles("teacher"))) -> list[SlipOut]:
    """The signed-in teacher's paid payslips, newest first."""
    return await service.my_slips(current_user)
