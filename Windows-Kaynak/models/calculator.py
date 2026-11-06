from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models.energy import EnergyCalculator
from models.factory import FactoryCalculator
from models.logistics import LogisticsCalculator
from models.metal import MetalCalculator
from models.personnel import PersonnelCalculator
from models.validation import non_negative, positive


MALIYET_ANA_LABELS = (
    ("elektrik", "Elektrik"),
    ("dogalgaz", "Doğalgaz"),
    ("su", "Su"),
    ("maas", "Maaş"),
    ("bina_kirasi", "Bina Kirası"),
    ("yemek", "Yemek"),
    ("arac_yakit", "Araç Yakıt"),
    ("genel_gider", "Genel Gider"),
    ("nakliye", "Nakliye"),
    ("tenefer", "Tenefer"),
    ("kalip_maliyeti", "Kalıp Maliyeti"),
    ("fabrika_is_akisi", "Fabrika İş Akışı"),
    ("amortisman", "Amortisman"),
    ("fabrika_fire_fason", "Fabrika Fire-Fason"),
    ("paketleme", "Paketleme Maliyeti"),
)


class CostCalculator:
    """Bütün maliyet modüllerini koordine eden ana hesaplayıcı."""

    def ayarlari_yukle(self) -> dict[str, float]:
        settings_path = Path(__file__).resolve().parents[1] / "data" / "settings.json"
        try:
            with settings_path.open("r", encoding="utf-8") as settings_file:
                data = json.load(settings_file)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

        return data if isinstance(data, dict) else {}

    def hesapla(
        self,
        uretim: float,
        lme: float,
        prim: float,
        usd: float,
        elektrik_fiyat: float,
        gaz_fiyat: float,
        iscilik: float,
        sgk: float = 0,
        yemek: float = 0,
        ambalaj: float = 0,
        genel_gider: float = 0,
        su_birim_fiyat: float = 106.31,
        mazot: float = 0,
        kira: float = 0,
        nakliye: float = 0,
        kalip: float = 0,
        bakim: float = 0,
        amortisman: float = 0,
        sarf: float = 0,
        tenefer: float = 0,
        diger: float = 0,
        gaz_kullanim: float = 0,
        gaz_otv: float = 0,
        elektrik_kwh_ton: float = 567,
        gaz_sm3_ton: float = 48,
        su_m3_ton: float = 0.5,
        tenefer_nakliye: float = 0,
        ekipman: float = 0,
        fire_orani: float = 0.15,
        ergitme_kaybi_orani: float = 0.03,
        fason_usd_kg: float = 0.25,
    ) -> dict[str, Any]:
        uretim = positive("Üretim", uretim)
        usd = positive("USD/TL kuru", usd)
        ambalaj = non_negative("Paketleme gideri", ambalaj)

        # Alt sekmelerden gelen değerler, seçili ayın gerçek toplamlarıdır.
        # Üretime göre ikinci kez ölçeklenmeden doğrudan hesaba alınırlar.
        aylik_detay_giderleri = {
            "kalip": non_negative("Kalıp", kalip),
            "sarf": non_negative("Sarf malzemesi", sarf),
            "ekipman": non_negative("Ekipman", ekipman),
            "mazot": non_negative("Mazot", mazot),
            "nakliye": non_negative("Nakliye", nakliye),
            "tenefer_nakliye": non_negative(
                "Tenefer nakliye", tenefer_nakliye
            ),
            "tenefer": non_negative("Tenefer", tenefer),
        }

        metal = MetalCalculator().hesapla(
            uretim,
            lme,
            prim,
            usd,
            fire_orani,
            ergitme_kaybi_orani,
            fason_usd_kg,
        )
        enerji = EnergyCalculator().hesapla(
            uretim,
            elektrik_fiyat,
            gaz_fiyat,
            su_birim_fiyat,
            gaz_kullanim,
            gaz_otv,
            elektrik_kwh_ton,
            gaz_sm3_ton,
            su_m3_ton,
        )
        personel = PersonnelCalculator().hesapla(iscilik, sgk, yemek)
        fabrika = FactoryCalculator().hesapla(
            kira,
            amortisman,
            bakim,
            aylik_detay_giderleri["kalip"],
            aylik_detay_giderleri["sarf"],
            genel_gider,
            aylik_detay_giderleri["ekipman"],
        )
        lojistik = LogisticsCalculator().hesapla(
            mazot=aylik_detay_giderleri["mazot"],
            nakliye=aylik_detay_giderleri["nakliye"],
            tenefer_nakliye=aylik_detay_giderleri["tenefer_nakliye"],
            tenefer=aylik_detay_giderleri["tenefer"],
            diger=diger,
        )

        metal_toplam = metal["toplam"]
        enerji_toplam = enerji["toplam"]
        personel_toplam = personel["toplam"]
        temel_fabrika_giderleri = fabrika["toplam"]
        fire_toplam = metal["fire_toplam"]
        fabrika_giderleri = temel_fabrika_giderleri + fire_toplam
        lojistik_giderleri = lojistik["toplam"]
        sabit_giderler = (
            personel_toplam
            + fabrika["kira"]
            + fabrika["amortisman"]
            + fabrika["bakim"]
            + fabrika["genel_gider"]
            + lojistik["diger"]
        )

        # "Diğer" gider lojistik modülünün toplamında zaten bulunur. Burada
        # yeniden eklenmemesi, önceki sürümdeki çift sayım hatasını düzeltir.
        fabrika_toplam = (
            personel_toplam + fabrika_giderleri + lojistik_giderleri
        )
        donusum_toplam = enerji_toplam + fabrika_toplam + ambalaj

        # Maliyet Ana ekranındaki 15 kalem. Kullanıcının talebine göre
        # hammadde (net metal) bu tablonun dışında tutulur; fire/fason ise
        # dönüşüm maliyetinin bir parçası olarak tabloda yer alır.
        maliyet_ana_tl = {
            "elektrik": enerji["elektrik_maliyet"],
            "dogalgaz": enerji["gaz_maliyet"],
            "su": enerji["su_maliyet"],
            "maas": personel["iscilik"] + personel["sgk"],
            "bina_kirasi": fabrika["kira"],
            "yemek": personel["yemek"],
            "arac_yakit": lojistik["mazot"],
            "genel_gider": fabrika["genel_gider"] + lojistik["diger"],
            "nakliye": lojistik["nakliye"] + lojistik["tenefer_nakliye"],
            "tenefer": lojistik["tenefer"],
            "kalip_maliyeti": fabrika["kalip"],
            "fabrika_is_akisi": (
                fabrika["sarf"] + fabrika["ekipman"] + fabrika["bakim"]
            ),
            "amortisman": fabrika["amortisman"],
            "fabrika_fire_fason": fire_toplam,
            "paketleme": ambalaj,
        }
        maliyet_ana_toplam_tl = sum(maliyet_ana_tl.values())
        maliyet_ana_usd = {
            key: value / usd for key, value in maliyet_ana_tl.items()
        }
        maliyet_ana_usd_kg = {
            key: value / uretim
            for key, value in maliyet_ana_usd.items()
        }
        maliyet_ana_usd_ton = {
            key: value * 1000
            for key, value in maliyet_ana_usd_kg.items()
        }
        maliyet_ana_toplam_usd = maliyet_ana_toplam_tl / usd
        maliyet_ana_usd_kg_toplam = maliyet_ana_toplam_usd / uretim
        maliyet_ana_usd_ton_toplam = maliyet_ana_usd_kg_toplam * 1000
        return {
            # Hammadde
            "billet_usd": metal["billet_usd"],
            "billet_usd_kg": metal["billet_usd_kg"],
            "billet_tl": metal["billet_tl"],
            "fire_orani": metal["fire_orani"],
            "ergitme_kaybi_orani": metal["ergitme_kaybi_orani"],
            "fason_usd_kg": metal["fason_usd_kg"],
            "billet_ihtiyaci": metal["billet_ihtiyaci"],
            "brut_billet_maliyeti": metal["brut_billet_maliyeti"],
            "fire": metal["fire"],
            "geri_donusum": metal["geri_donusum"],
            "ergitme": metal["ergitme"],
            "metal_kaybi": metal["metal_kaybi"],
            "fason": metal["fason"],
            "fire_toplam": fire_toplam,
            "billet_maliyet": metal["billet_maliyet"],
            "metal_toplam": metal_toplam,
            "sabit_giderler": sabit_giderler,
            # Enerji
            "elektrik_kwh_ton": enerji["elektrik_kwh_ton"],
            "gaz_sm3_ton": enerji["gaz_sm3_ton"],
            "su_m3_ton": enerji["su_m3_ton"],
            "gaz_birim_toplam": enerji["gaz_birim_toplam"],
            "elektrik_tuketim": enerji["elektrik_tuketim"],
            "gaz_tuketim": enerji["gaz_tuketim"],
            "su_tuketim": enerji["su_tuketim"],
            "elektrik_maliyet": enerji["elektrik_maliyet"],
            "gaz_maliyet": enerji["gaz_maliyet"],
            "su_maliyet": enerji["su_maliyet"],
            "enerji_toplam": enerji_toplam,
            # Personel
            "iscilik": personel["iscilik"],
            "sgk": personel["sgk"],
            "yemek": personel["yemek"],
            "personel_toplam": personel_toplam,
            # Fabrika
            "kira": fabrika["kira"],
            "amortisman": fabrika["amortisman"],
            "bakim": fabrika["bakim"],
            "kalip": fabrika["kalip"],
            "sarf": fabrika["sarf"],
            "ekipman": fabrika["ekipman"],
            "genel_gider": fabrika["genel_gider"],
            "temel_fabrika_giderleri": temel_fabrika_giderleri,
            "fabrika_giderleri": fabrika_giderleri,
            # Lojistik ve diğer
            "mazot": lojistik["mazot"],
            "nakliye": lojistik["nakliye"],
            "tenefer_nakliye": lojistik["tenefer_nakliye"],
            "tenefer": lojistik["tenefer"],
            "diger": lojistik["diger"],
            "lojistik_giderleri": lojistik_giderleri,
            # Paketleme ve özetler
            "ambalaj": ambalaj,
            "fabrika_toplam": fabrika_toplam,
            "genel_toplam": fabrika_toplam + ambalaj,
            "donusum_toplam": donusum_toplam,
            # Maliyet Ana — 15 kalem
            "maliyet_ana_labels": dict(MALIYET_ANA_LABELS),
            "maliyet_ana_tl": maliyet_ana_tl,
            "maliyet_ana_usd": maliyet_ana_usd,
            "maliyet_ana_usd_kg": maliyet_ana_usd_kg,
            "maliyet_ana_usd_ton": maliyet_ana_usd_ton,
            "maliyet_ana_toplam_tl": maliyet_ana_toplam_tl,
            "maliyet_ana_toplam_usd": maliyet_ana_toplam_usd,
            "maliyet_ana_usd_kg_toplam": maliyet_ana_usd_kg_toplam,
            "maliyet_ana_usd_ton_toplam": maliyet_ana_usd_ton_toplam,
        }
