from __future__ import annotations

import math

from models.validation import non_negative, positive


class PackagingCalculator:
    """Excel'deki palet ve paketleme formüllerini uygular."""

    def hesapla(
        self,
        strec: float = 0,
        naylon: float = 0,
        cember: float = 0,
        kosebent: float = 0,
        etiket: float = 0,
    ) -> dict[str, float]:
        """Önceden hesaplanmış aylık paketleme tutarlarını toplar."""
        values = {
            "strec": non_negative("Streç film", strec),
            "naylon": non_negative("Sarma naylonu", naylon),
            "cember": non_negative("Çember", cember),
            "kosebent": non_negative("Köşebent", kosebent),
            "etiket": non_negative("Etiket", etiket),
        }
        return {**values, "toplam": sum(values.values())}

    def excel_hesapla(
        self,
        uretim: float,
        usd: float,
        ortalama_palet_kg: float = 650,
        yansiz_oran: float = 0.75,
        kereste_m3_fiyat: float = 14_000,
        kosebent_birim_fiyat: float = 12.25,
        cember_1000mt_fiyat: float = 2_000,
        naylon_kg_palet: float = 8,
        naylon_usd_ton: float = 3_100,
        strec_adet: float = 168,
        strec_birim_fiyat: float = 48,
        etiket: float = 0,
        referans_uretim: float = 200_000,
        takoz_adet: float = 3,
        takoz_boy_m: float = 0.70,
        takoz_en_m: float = 0.07,
        takoz_yukseklik_m: float = 0.08,
        ust_kereste_adet: float = 3,
        ust_kereste_boy_m: float = 0.70,
        ust_kereste_en_m: float = 0.02,
        ust_kereste_yukseklik_m: float = 0.10,
        yan_kereste_adet: float = 6,
        yan_kereste_boy_m: float = 0.70,
        yan_kereste_en_m: float = 0.02,
        yan_kereste_yukseklik_m: float = 0.10,
        kosebent_adet_palet: float = 2,
        cember_mt_palet: float = 14,
        cember_fiyat_metresi: float = 1_000,
        naylon_sarim_orani: float | None = None,
    ) -> dict[str, float]:
        uretim = positive("Üretim", uretim)
        usd = positive("USD/TL kuru", usd)
        referans_uretim = positive("Referans üretim", referans_uretim)
        ortalama_palet_kg = positive(
            "Ortalama palet ağırlığı", ortalama_palet_kg
        )
        yansiz_oran = non_negative("Yansız palet oranı", yansiz_oran)
        if yansiz_oran > 1:
            raise ValueError("Yansız palet oranı 0 ile 1 arasında olmalıdır.")
        if naylon_sarim_orani is None:
            naylon_sarim_orani = yansiz_oran
        naylon_sarim_orani = non_negative(
            "Sarma naylon kullanılan palet oranı",
            naylon_sarim_orani,
        )
        if naylon_sarim_orani > 1:
            raise ValueError(
                "Sarma naylon oranı 0 ile 1 arasında olmalıdır."
            )

        values = {
            "kereste_m3_fiyat": non_negative(
                "Kereste m³ fiyatı", kereste_m3_fiyat
            ),
            "kosebent_birim_fiyat": non_negative(
                "Köşebent birim fiyatı", kosebent_birim_fiyat
            ),
            "cember_1000mt_fiyat": non_negative(
                "Çember 1000 metre fiyatı", cember_1000mt_fiyat
            ),
            "naylon_kg_palet": non_negative(
                "Palet başı naylon", naylon_kg_palet
            ),
            "naylon_usd_ton": non_negative(
                "Naylon USD/ton fiyatı", naylon_usd_ton
            ),
            "strec_adet": non_negative("Streç adedi", strec_adet),
            "strec_birim_fiyat": non_negative(
                "Streç birim fiyatı", strec_birim_fiyat
            ),
            "etiket": non_negative("Etiket gideri", etiket),
            "takoz_adet": non_negative("Takoz adedi", takoz_adet),
            "takoz_boy_m": non_negative("Takoz boyu", takoz_boy_m),
            "takoz_en_m": non_negative("Takoz eni", takoz_en_m),
            "takoz_yukseklik_m": non_negative(
                "Takoz yüksekliği", takoz_yukseklik_m
            ),
            "ust_kereste_adet": non_negative(
                "Üst kereste adedi", ust_kereste_adet
            ),
            "ust_kereste_boy_m": non_negative(
                "Üst kereste boyu", ust_kereste_boy_m
            ),
            "ust_kereste_en_m": non_negative(
                "Üst kereste eni", ust_kereste_en_m
            ),
            "ust_kereste_yukseklik_m": non_negative(
                "Üst kereste yüksekliği", ust_kereste_yukseklik_m
            ),
            "yan_kereste_adet": non_negative(
                "Yan kereste adedi", yan_kereste_adet
            ),
            "yan_kereste_boy_m": non_negative(
                "Yan kereste boyu", yan_kereste_boy_m
            ),
            "yan_kereste_en_m": non_negative(
                "Yan kereste eni", yan_kereste_en_m
            ),
            "yan_kereste_yukseklik_m": non_negative(
                "Yan kereste yüksekliği", yan_kereste_yukseklik_m
            ),
            "kosebent_adet_palet": non_negative(
                "Palet başı köşebent", kosebent_adet_palet
            ),
            "cember_mt_palet": non_negative(
                "Palet başı çember", cember_mt_palet
            ),
        }
        cember_fiyat_metresi = positive(
            "Çember fiyatının geçerli olduğu metre",
            cember_fiyat_metresi,
        )

        palet_adedi = math.ceil(uretim / ortalama_palet_kg)
        yansiz_palet = palet_adedi * yansiz_oran
        yanli_palet = palet_adedi - yansiz_palet

        takoz_m3 = (
            values["takoz_adet"]
            * values["takoz_boy_m"]
            * values["takoz_en_m"]
            * values["takoz_yukseklik_m"]
        )
        ust_kereste_m3 = (
            values["ust_kereste_adet"]
            * values["ust_kereste_boy_m"]
            * values["ust_kereste_en_m"]
            * values["ust_kereste_yukseklik_m"]
        )
        yan_kereste_m3 = (
            values["yan_kereste_adet"]
            * values["yan_kereste_boy_m"]
            * values["yan_kereste_en_m"]
            * values["yan_kereste_yukseklik_m"]
        )
        yansiz_palet_m3 = takoz_m3 + ust_kereste_m3
        yanli_palet_m3 = yansiz_palet_m3 + yan_kereste_m3
        kereste_m3 = (
            yansiz_palet * yansiz_palet_m3
            + yanli_palet * yanli_palet_m3
        )
        kereste = kereste_m3 * values["kereste_m3_fiyat"]
        kosebent_adedi = palet_adedi * values["kosebent_adet_palet"]
        kosebent = (
            kosebent_adedi * values["kosebent_birim_fiyat"]
        )
        cember_mt = palet_adedi * values["cember_mt_palet"]
        cember = (
            cember_mt
            / cember_fiyat_metresi
            * values["cember_1000mt_fiyat"]
        )
        naylon_palet_adedi = palet_adedi * naylon_sarim_orani
        naylon_kg = naylon_palet_adedi * values["naylon_kg_palet"]
        naylon_tl_kg = values["naylon_usd_ton"] / 1000 * usd
        naylon = (
            naylon_kg
            * values["naylon_usd_ton"]
            / 1000
            * usd
        )
        # Kullanıcının kuralı: 200.000 kg net üretimde 168 adet.
        # Parçalı sonuçta malzeme eksik kalmaması için yukarı yuvarlanır.
        uretim_orani = uretim / referans_uretim
        strec_adedi = math.ceil(values["strec_adet"] * uretim_orani)
        etiket = values["etiket"] * uretim_orani
        strec = strec_adedi * values["strec_birim_fiyat"]
        toplam = (
            kereste
            + kosebent
            + cember
            + naylon
            + strec
            + etiket
        )

        return {
            "palet_adedi": float(palet_adedi),
            "uretim_orani": uretim_orani,
            "yansiz_palet": yansiz_palet,
            "yanli_palet": yanli_palet,
            "takoz_m3": takoz_m3,
            "ust_kereste_m3": ust_kereste_m3,
            "yan_kereste_m3": yan_kereste_m3,
            "yansiz_palet_m3": yansiz_palet_m3,
            "yanli_palet_m3": yanli_palet_m3,
            "kereste_m3": kereste_m3,
            "kereste": kereste,
            "kereste_m3_fiyat": values["kereste_m3_fiyat"],
            "kosebent_adedi": kosebent_adedi,
            "kosebent_birim_fiyat": values["kosebent_birim_fiyat"],
            "kosebent": kosebent,
            "cember_mt": cember_mt,
            "cember_tl_mt": (
                values["cember_1000mt_fiyat"] / cember_fiyat_metresi
            ),
            "cember": cember,
            "naylon_palet_adedi": naylon_palet_adedi,
            "naylon_kg": naylon_kg,
            "naylon_tl_kg": naylon_tl_kg,
            "naylon": naylon,
            "strec_adedi": strec_adedi,
            "strec_birim_fiyat": values["strec_birim_fiyat"],
            "strec": strec,
            "etiket": etiket,
            "toplam": toplam,
        }
