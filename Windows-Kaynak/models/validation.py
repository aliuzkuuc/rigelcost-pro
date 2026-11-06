from __future__ import annotations

import math


def as_number(name: str, value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} sayısal bir değer olmalıdır.") from exc

    if not math.isfinite(number):
        raise ValueError(f"{name} geçerli bir sayı olmalıdır.")
    return number


def non_negative(name: str, value: float) -> float:
    number = as_number(name, value)
    if number < 0:
        raise ValueError(f"{name} sıfırdan küçük olamaz.")
    return number


def positive(name: str, value: float) -> float:
    number = as_number(name, value)
    if number <= 0:
        raise ValueError(f"{name} sıfırdan büyük olmalıdır.")
    return number
