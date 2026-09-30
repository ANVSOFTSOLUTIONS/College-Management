import re


def normalize_indian_mobile(phone: str) -> str | None:
    """Returns 91XXXXXXXXXX for a valid Indian mobile number, else None."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10:
        digits = "91" + digits
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return digits
    return None
