import re
import zlib

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.modules import LEGACY_MODULES, OPTIONAL_MODULES

# Public-site templates; the frontend renders each (frontend/src/siteTemplates).
TEMPLATE_IDS = ["classic", "modern", "vibrant", "emerald", "royal", "neon", "sunrise", "ocean", "editorial", "split"]
ALLOWED_TEMPLATES = set(TEMPLATE_IDS)
# Every school can use these; the rest need Pro (switched on by the super admin once paid).
FREE_TEMPLATES = ["classic", "modern"]


def auto_template(code: str) -> str:
    """A new school gets a free template picked from its code, so neighbouring schools don't all look alike."""
    return FREE_TEMPLATES[zlib.crc32(code.upper().encode()) % len(FREE_TEMPLATES)]
ALLOWED_MODULES = set(OPTIONAL_MODULES) | LEGACY_MODULES
ALLOWED_BILLING_STATUSES = {"trial", "active", "suspended"}
# Online payment gateways a school may connect its own account to (see app/integrations/gateways.py).
PAYMENT_GATEWAYS = ["cashfree", "razorpay", "phonepe", "demo"]  # demo: pretend payments for showing the product
_SUBDOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$")


def _validate_subdomain(value: str) -> str:
    normalized = value.strip().lower()
    if not _SUBDOMAIN_PATTERN.match(normalized):
        raise ValueError(
            "Subdomain must be lowercase letters, numbers, and hyphens only (not starting/ending with a hyphen)."
        )
    return normalized


def _validate_template(value: str) -> str:
    if value not in ALLOWED_TEMPLATES:
        raise ValueError(f"Template must be one of: {', '.join(sorted(ALLOWED_TEMPLATES))}.")
    return value


def _validate_modules(value: list[str]) -> list[str]:
    unknown = sorted(set(value) - ALLOWED_MODULES)
    if unknown:
        raise ValueError(f"Unknown module(s): {', '.join(unknown)}. Allowed: {', '.join(sorted(ALLOWED_MODULES))}.")
    return sorted(set(value))


def _validate_gateways(value: list[str]) -> list[str]:
    unknown = sorted(set(value) - set(PAYMENT_GATEWAYS))
    if unknown:
        raise ValueError(f"Unknown payment gateway(s): {', '.join(unknown)}. Allowed: {', '.join(PAYMENT_GATEWAYS)}.")
    return [g for g in PAYMENT_GATEWAYS if g in value]


def _validate_billing_status(value: str) -> str:
    if value not in ALLOWED_BILLING_STATUSES:
        raise ValueError(f"Billing status must be one of: {', '.join(sorted(ALLOWED_BILLING_STATUSES))}.")
    return value


class CreateSchoolRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=2, max_length=30)
    subdomain: str | None = Field(default=None, min_length=3, max_length=40)
    template: str | None = None  # omitted: picked automatically
    enabled_modules: list[str] = Field(default_factory=lambda: list(OPTIONAL_MODULES))
    monthly_fee: float = Field(default=600, ge=0)
    billing_status: str = "trial"
    admin_email: EmailStr
    admin_full_name: str = Field(min_length=1, max_length=200)
    admin_password: str = Field(min_length=8, max_length=72)

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("subdomain")
    @classmethod
    def _normalize_subdomain(cls, value: str | None) -> str | None:
        return _validate_subdomain(value) if value else value

    @field_validator("template")
    @classmethod
    def _check_template(cls, value: str | None) -> str | None:
        return _validate_template(value) if value else value

    @field_validator("enabled_modules")
    @classmethod
    def _check_modules(cls, value: list[str]) -> list[str]:
        return _validate_modules(value)

    @field_validator("billing_status")
    @classmethod
    def _check_billing_status(cls, value: str) -> str:
        return _validate_billing_status(value)


class UpdateSchoolRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    subdomain: str | None = Field(default=None, min_length=3, max_length=40)
    template: str | None = None
    enabled_modules: list[str] | None = None
    monthly_fee: float | None = Field(default=None, ge=0)
    billing_status: str | None = None
    status: str | None = None
    pro_templates: bool | None = None
    payment_gateways: list[str] | None = None  # the gateways the school may choose from

    @field_validator("payment_gateways")
    @classmethod
    def _check_gateways(cls, value: list[str] | None) -> list[str] | None:
        return _validate_gateways(value) if value is not None else value

    @field_validator("subdomain")
    @classmethod
    def _normalize_subdomain(cls, value: str | None) -> str | None:
        return _validate_subdomain(value) if value else value

    @field_validator("template")
    @classmethod
    def _check_template(cls, value: str | None) -> str | None:
        return _validate_template(value) if value else value

    @field_validator("enabled_modules")
    @classmethod
    def _check_modules(cls, value: list[str] | None) -> list[str] | None:
        return _validate_modules(value) if value is not None else value

    @field_validator("billing_status")
    @classmethod
    def _check_billing_status(cls, value: str | None) -> str | None:
        return _validate_billing_status(value) if value else value

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str | None) -> str | None:
        if value is not None and value not in {"active", "inactive"}:
            raise ValueError("Status must be 'active' or 'inactive'.")
        return value


class SchoolSummary(BaseModel):
    id: str
    name: str
    code: str
    subdomain: str
    template: str
    enabled_modules: list[str]
    monthly_fee: float
    billing_status: str
    status: str
    pro_templates: bool = False
    payment_gateways: list[str] = []


class CreateSchoolResponse(BaseModel):
    school: SchoolSummary
    admin_email: str
