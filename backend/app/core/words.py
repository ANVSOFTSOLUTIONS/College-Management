"""Numbers and dates in words, as Indian school documents print them."""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

_ONES = "Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen".split()
_TENS = "_ _ Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety".split()
_ORDINALS = {
    1: "First", 2: "Second", 3: "Third", 4: "Fourth", 5: "Fifth", 6: "Sixth", 7: "Seventh", 8: "Eighth", 9: "Ninth", 10: "Tenth",
    11: "Eleventh", 12: "Twelfth", 13: "Thirteenth", 14: "Fourteenth", 15: "Fifteenth", 16: "Sixteenth", 17: "Seventeenth",
    18: "Eighteenth", 19: "Nineteenth", 20: "Twentieth", 30: "Thirtieth",
}


def number_words(n: int) -> str:
    """Western grouping (thousands), as years are read: 2016 -> "Two Thousand Sixteen"."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else f"-{_ONES[n % 10]}")
    if n < 1000:
        rest = n % 100
        return f"{_ONES[n // 100]} Hundred" + (f" {number_words(rest)}" if rest else "")
    rest = n % 1000
    return f"{number_words(n // 1000)} Thousand" + (f" {number_words(rest)}" if rest else "")


def _indian_words(n: int) -> str:
    """Indian grouping: 125000 -> "One Lakh Twenty-Five Thousand"."""
    parts = []
    for size, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand")):
        if n >= size:
            parts.append(f"{_indian_words(n // size) if size == 10_000_000 else number_words(n // size)} {name}")
            n %= size
    if n or not parts:
        parts.append(number_words(n))
    return " ".join(parts)


def rupees_in_words(amount: float | Decimal) -> str:
    """25000.5 -> "Rupees Twenty-Five Thousand and Fifty Paise Only"."""
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    rupees, paise = int(value), int((value - int(value)) * 100)
    text = f"Rupees {_indian_words(rupees)}"
    if paise:
        text += f" and {number_words(paise)} Paise"
    return f"{text} Only"


def date_in_words(value: date) -> str:
    """12 April 2016 -> "Twelfth April Two Thousand Sixteen" (as TCs write the date of birth)."""
    day = value.day
    ordinal = _ORDINALS.get(day) or f"{_TENS[day // 10]}-{_ORDINALS[day % 10]}"
    return f"{ordinal} {value:%B} {number_words(value.year)}"
