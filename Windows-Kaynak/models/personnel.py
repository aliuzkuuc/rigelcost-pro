from __future__ import annotations

from models.validation import non_negative


class PersonnelCalculator:
    def hesapla(
        self,
        iscilik: float = 0,
        sgk: float = 0,
        yemek: float = 0,
    ) -> dict[str, float]:
        iscilik = non_negative("İşçilik", iscilik)
        sgk = non_negative("SGK", sgk)
        yemek = non_negative("Yemek", yemek)

        return {
            "iscilik": iscilik,
            "sgk": sgk,
            "yemek": yemek,
            "toplam": iscilik + sgk + yemek,
        }
