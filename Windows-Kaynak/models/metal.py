from __future__ import annotations

from models.validation import non_negative, positive


class MetalCalculator:
    """Net üretim, brüt billet ve fire geri dönüşümünü hesaplar."""

    FIRE_ORANI = 0.15
    ERGITME_KAYBI = 0.03
    FASON_ERGITME = 0.25  # USD/kg

    def hesapla(
        self,
        uretim: float,
        lme: float,
        prim: float,
        usd: float,
        fire_orani: float = FIRE_ORANI,
        ergitme_kaybi_orani: float = ERGITME_KAYBI,
        fason_usd_kg: float = FASON_ERGITME,
    ) -> dict[str, float]:
        uretim = positive("Üretim", uretim)
        lme = non_negative("LME", lme)
        prim = non_negative("Prim", prim)
        usd = positive("USD/TL kuru", usd)
        fire_orani = non_negative("Fabrika fire oranı", fire_orani)
        ergitme_kaybi_orani = non_negative(
            "Ergitme kayıp oranı", ergitme_kaybi_orani
        )
        fason_usd_kg = non_negative("Fason ergitme fiyatı", fason_usd_kg)
        if fire_orani >= 1:
            raise ValueError("Fabrika fire oranı %100'den küçük olmalıdır.")
        if ergitme_kaybi_orani > 1:
            raise ValueError("Ergitme kayıp oranı %100'ü geçemez.")

        billet_usd = lme + prim
        billet_usd_kg = billet_usd / 1000
        billet_tl_kg = billet_usd_kg * usd

        # Excel referansı:
        # Brüt billet -> net üretim + ilk fire
        # İlk firenin %97'si geri döner, %3'ü nihai metal kaybıdır.
        billet_ihtiyaci = uretim / (1 - fire_orani)
        fire = billet_ihtiyaci - uretim
        geri_donusum = fire * (1 - ergitme_kaybi_orani)
        ergitme_kaybi = fire - geri_donusum

        # Fason ergitme yalnız geri dönen fireye uygulanır.
        fason = geri_donusum * fason_usd_kg * usd
        metal_kaybi = ergitme_kaybi * billet_tl_kg
        fire_toplam = fason + metal_kaybi

        # Billet fiyatı net profile bir kez uygulanır. Brüt billet maliyeti
        # bilgi amaçlıdır; toplam maliyete ikinci kez girmez.
        billet_maliyet = uretim * billet_tl_kg
        brut_billet_maliyeti = billet_ihtiyaci * billet_tl_kg

        return {
            "billet_usd": billet_usd,
            "billet_usd_kg": billet_usd_kg,
            "billet_tl": billet_tl_kg,
            "fire_orani": fire_orani,
            "ergitme_kaybi_orani": ergitme_kaybi_orani,
            "fason_usd_kg": fason_usd_kg,
            "billet_ihtiyaci": billet_ihtiyaci,
            "brut_billet_maliyeti": brut_billet_maliyeti,
            "fire": fire,
            "geri_donusum": geri_donusum,
            "ergitme": ergitme_kaybi,
            "metal_kaybi": metal_kaybi,
            "fason": fason,
            "fire_toplam": fire_toplam,
            "billet_maliyet": billet_maliyet,
            "toplam": billet_maliyet,
        }
