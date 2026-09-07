"""Whole dollars at the presentation boundary; the ledger retains integer cents."""
from decimal import Decimal, ROUND_HALF_UP
import re
from markupsafe import Markup


def dollars(value):
    return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def money(cents):
    value = dollars(Decimal(str(cents)) / 100)
    return ('−' if value < 0 else '') + f'${abs(value):,}'


_CURRENCY = re.compile(r'([−-]?)\$([−-]?)(\d[\d,]*\.\d+)')
_OLD_SALARY = re.compile(r'((?:monthly base pay|previous pay) )(\d[\d,]*\.\d+)')


def whole_money_text(value):
    """Render legacy event/preview text without rewriting persisted history."""
    if not isinstance(value, str):
        return value
    def replace(match):
        amount = Decimal(match[3].replace(',', ''))
        if match[1] or match[2]: amount = -amount
        rounded = dollars(amount)
        return ('−' if rounded < 0 else '') + f'${abs(rounded):,}'
    text = _CURRENCY.sub(replace, value)
    text = _OLD_SALARY.sub(lambda m: m[1] + f"{dollars(m[2].replace(',', '')):,}", text)
    return Markup(text) if isinstance(value, Markup) else text


def display_payload(value):
    if isinstance(value, dict):
        return {key: display_payload(item) for key,item in value.items()}
    if isinstance(value, (list, tuple)):
        return [display_payload(item) for item in value]
    return whole_money_text(value)
