from __future__ import annotations

from models.validation import non_negative


class LogisticsCalculator:
    def hesapla(
        self,
        mazot: float = 0,
        nakliye: float = 0,
        tenefer_nakliye: float = 0,
        tenefer: float = 0,
        diger: float = 0,
    ) -> dict[str, float]:
        values = {
            "mazot": non_negative("Mazot", mazot),
            "nakliye": non_negative("Nakliye", nakliye),
            "tenefer_nakliye": non_negative(
                "Tenefer nakliye", tenefer_nakliye
            ),
            "tenefer": non_negative("Tenefer", tenefer),
            "diger": non_negative("Diğer gider", diger),
        }
        return {**values, "toplam": sum(values.values())}
