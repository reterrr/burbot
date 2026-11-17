"""Validate JSON business values against a current field definition."""

import json
import math
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID


def validate_value(value, definition: dict):
    if value is None:
        if not definition.get("nullable", True):
            raise ValueError("Field does not allow null")
        return
    kind = definition["type"]
    if kind in ("string", "text"):
        if not isinstance(value, str):
            raise ValueError("Expected a string")
        if definition.get("min_length") is not None and len(value) < definition["min_length"]:
            raise ValueError("Value is shorter than min_length")
        if definition.get("max_length") is not None and len(value) > definition["max_length"]:
            raise ValueError("Value is longer than max_length")
        if definition.get("pattern") and re.search(definition["pattern"], value) is None:
            raise ValueError("Value does not match pattern")
    elif kind in ("integer", "biginteger", "reference", "source"):
        if type(value) is not int:
            raise ValueError("Expected an integer")
        bits = 32 if kind == "integer" else 64
        if not -(2 ** (bits - 1)) <= value < 2 ** (bits - 1):
            raise ValueError(f"Value exceeds signed {bits}-bit range")
        if kind in ("reference", "source") and value <= 0:
            raise ValueError("Reference ID must be positive")
    elif kind == "float":
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Expected a finite number")
    elif kind == "decimal":
        if type(value) not in (int, float, str):
            raise ValueError("Expected a decimal number or string")
        if isinstance(value, str) and not re.fullmatch(
            r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?",
            value,
        ):
            raise ValueError("Expected a canonical decimal string")
        try:
            number = Decimal(str(value))
        except InvalidOperation as error:
            raise ValueError("Invalid decimal") from error
        if not number.is_finite():
            raise ValueError("Expected a finite decimal")
        _, digits, exponent = number.as_tuple()
        scale = max(-exponent, 0)
        integral = max(len(digits) + exponent, 0)
        if definition.get("scale") is not None and scale > definition["scale"]:
            raise ValueError("Value exceeds decimal scale")
        precision = definition.get("precision")
        if precision is not None and integral + scale > precision:
            raise ValueError("Value exceeds decimal precision")
        if precision is not None and definition.get("scale") is not None:
            if integral > precision - definition["scale"]:
                raise ValueError("Value exceeds decimal integer digits")
    elif kind == "enum":
        allowed = definition.get("enum_values", [])
        if not any(type(value) is type(member) and value == member for member in allowed):
            raise ValueError("Value is not a member of the declared enum")
    elif kind == "boolean":
        if type(value) is not bool:
            raise ValueError("Expected a boolean")
    elif kind in ("date", "datetime", "uuid"):
        if not isinstance(value, str):
            raise ValueError(f"Expected an ISO {kind} string")
        if kind == "date":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("Expected an ISO YYYY-MM-DD date")
            date.fromisoformat(value)
        elif kind == "datetime":
            if not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})", value
            ):
                raise ValueError("Expected a timezone-aware ISO datetime")
            if int(value[11:13]) > 23 or int(value[14:16]) > 59 or int(value[17:19]) > 59:
                raise ValueError("Invalid datetime time component")
            if not value.endswith("Z") and (int(value[-5:-3]) > 23 or int(value[-2:]) > 59):
                raise ValueError("Invalid datetime timezone offset")
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError("Datetime value must include a timezone offset")
        else:
            if not re.fullmatch(
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                value,
            ):
                raise ValueError("Expected a hyphenated UUID")
            UUID(value)
    elif kind != "json":
        raise ValueError(f"Unsupported field type: {kind}")
    if kind in ("integer", "biginteger", "float", "decimal"):
        number = Decimal(str(value))
        comparisons = {
            "gt": lambda bound: number > bound,
            "ge": lambda bound: number >= bound,
            "lt": lambda bound: number < bound,
            "le": lambda bound: number <= bound,
        }
        for constraint, check in comparisons.items():
            bound = definition.get(constraint)
            if bound is not None and not check(Decimal(str(bound))):
                raise ValueError(f"Value violates {constraint}={bound}")
    json.dumps(value, allow_nan=False)
