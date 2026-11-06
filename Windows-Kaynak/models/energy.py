from __future__ import annotations

from models.validation import non_negative, positive


def elektrik_birim_fiyat_hesapla(
    aktif: float,
    osb_dagitim: float,
    iletim: float,
    yuzde: float,
) -> dict[str, float]:
    """elektrik birim fiyatı: üç kalem + yüzde ek payı."""
    aktif = non_negative("Aktif elektrik bedeli", aktif)
    osb_dagitim = non_negative("OSB dağıtım bedeli", osb_dagitim)
    iletim = non_negative("İletim bedeli", iletim)
    yuzde = non_negative("Elektrik yüzde payı", yuzde)
    alt_toplam = aktif + osb_dagitim + iletim
    birim_fiyat = alt_toplam * (1 + yuzde / 100)
    return {
        "elektrik_aktif": aktif,
        "elektrik_osb_dagitim": osb_dagitim,
        "elektrik_iletim": iletim,
        "elektrik_alt_toplam": alt_toplam,
        "elektrik_yuzde": yuzde,
        "elektrik_birim_fiyat": birim_fiyat,
    }


class EnergyCalculator:
    """Üretime bağlı elektrik, doğalgaz ve su maliyetlerini hesaplar."""

    ELEKTRIK_KWH_TON = 567
    GAZ_SM3_TON = 48
    SU_M3_TON = 0.5

    def hesapla(
        self,
        uretim: float,
        elektrik_fiyat: float,
        gaz_fiyat: float,
        su_birim_fiyat: float,
        gaz_kullanim: float = 0,
        gaz_otv: float = 0,
        elektrik_kwh_ton: float | None = None,
        gaz_sm3_ton: float | None = None,
        su_m3_ton: float | None = None,
    ) -> dict[str, float]:
        uretim = positive("Üretim", uretim)
        elektrik_fiyat = non_negative(
            "Elektrik birim fiyatı", elektrik_fiyat
        )
        gaz_fiyat = non_negative("Doğalgaz tüketim bedeli", gaz_fiyat)
        gaz_kullanim = non_negative("Doğalgaz kullanım bedeli", gaz_kullanim)
        gaz_otv = non_negative("Doğalgaz ÖTV", gaz_otv)
        su_birim_fiyat = non_negative("Su birim fiyatı", su_birim_fiyat)
        elektrik_kwh_ton = non_negative(
            "Elektrik tüketim katsayısı",
            self.ELEKTRIK_KWH_TON
            if elektrik_kwh_ton is None
            else elektrik_kwh_ton,
        )
        gaz_sm3_ton = non_negative(
            "Doğalgaz tüketim katsayısı",
            self.GAZ_SM3_TON if gaz_sm3_ton is None else gaz_sm3_ton,
        )
        su_m3_ton = non_negative(
            "Su tüketim katsayısı",
            self.SU_M3_TON if su_m3_ton is None else su_m3_ton,
        )

        uretim_ton = uretim / 1000
        elektrik_tuketim = uretim_ton * elektrik_kwh_ton
        gaz_tuketim = uretim_ton * gaz_sm3_ton
        su_tuketim = uretim_ton * su_m3_ton

        gaz_birim_toplam = gaz_fiyat + gaz_kullanim + gaz_otv
        elektrik_maliyet = elektrik_tuketim * elektrik_fiyat
        gaz_maliyet = gaz_tuketim * gaz_birim_toplam
        su_maliyet = su_tuketim * su_birim_fiyat
        toplam = elektrik_maliyet + gaz_maliyet + su_maliyet

        return {
            "elektrik_fiyat": elektrik_fiyat,
            "elektrik_kwh_ton": elektrik_kwh_ton,
            "gaz_sm3_ton": gaz_sm3_ton,
            "su_m3_ton": su_m3_ton,
            "gaz_birim_toplam": gaz_birim_toplam,
            "elektrik_tuketim": elektrik_tuketim,
            "gaz_tuketim": gaz_tuketim,
            "su_tuketim": su_tuketim,
            "elektrik_maliyet": elektrik_maliyet,
            "gaz_maliyet": gaz_maliyet,
            "su_maliyet": su_maliyet,
            "toplam": toplam,
        }
