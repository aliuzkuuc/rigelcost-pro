from __future__ import annotations

from models.validation import non_negative


class FactoryCalculator:
    def hesapla(
        self,
        kira: float = 0,
        amortisman: float = 0,
        bakim: float = 0,
        kalip: float = 0,
        sarf: float = 0,
        genel_gider: float = 0,
        ekipman: float = 0,
    ) -> dict[str, float]:
        values = {
            "kira": non_negative("Kira", kira),
            "amortisman": non_negative("Amortisman", amortisman),
            "bakim": non_negative("Bakım", bakim),
            "kalip": non_negative("Kalıp", kalip),
            "sarf": non_negative("Sarf malzemesi", sarf),
            "genel_gider": non_negative("Genel gider", genel_gider),
            "ekipman": non_negative("Ekipman", ekipman),
        }
        return {**values, "toplam": sum(values.values())}
