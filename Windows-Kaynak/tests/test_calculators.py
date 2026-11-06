from __future__ import annotations

import unittest

from models.calculator import CostCalculator
from models.energy import elektrik_birim_fiyat_hesapla
from models.packaging_calculator import PackagingCalculator


class CostCalculatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calculator = CostCalculator()
        self.inputs = {
            "uretim": 200_000,
            "lme": 3_192,
            "prim": 625,
            "usd": 42,
            "elektrik_fiyat": 2.97,
            "gaz_fiyat": 18.90,
            "iscilik": 1_000_000,
            "sgk": 250_000,
            "yemek": 120_000,
            "ambalaj": 80_000,
            "genel_gider": 150_000,
            "su_m3_ton": 0.5,
            "su_birim_fiyat": 106.31,
            "mazot": 50_000,
            "kira": 100_000,
            "nakliye": 90_000,
            "kalip": 40_000,
            "bakim": 60_000,
            "amortisman": 200_000,
            "sarf": 75_000,
            "tenefer": 25_000,
            "diger": 123_456,
        }

    def test_factory_total_equals_15_expense_items(self) -> None:
        result = self.calculator.hesapla(**self.inputs)
        self.assertAlmostEqual(
            result["maliyet_ana_toplam_tl"],
            sum(result["maliyet_ana_tl"].values()),
        )
        self.assertAlmostEqual(
            result["maliyet_ana_toplam_tl"],
            result["donusum_toplam"],
        )

    def test_other_expense_is_counted_once(self) -> None:
        with_other = self.calculator.hesapla(**self.inputs)
        without_other_inputs = {**self.inputs, "diger": 0}
        without_other = self.calculator.hesapla(**without_other_inputs)
        self.assertAlmostEqual(
            with_other["maliyet_ana_toplam_tl"]
            - without_other["maliyet_ana_toplam_tl"],
            self.inputs["diger"],
        )

    def test_excel_metal_formula_uses_net_production_once(self) -> None:
        result = self.calculator.hesapla(**self.inputs)
        raw_material_usd_ton = (
            result["billet_maliyet"]
            / self.inputs["uretim"]
            * 1000
            / self.inputs["usd"]
        )
        self.assertAlmostEqual(raw_material_usd_ton, 3_817)
        self.assertAlmostEqual(result["billet_ihtiyaci"], 200_000 / 0.85)
        self.assertAlmostEqual(
            result["fire"],
            result["billet_ihtiyaci"] - 200_000,
        )
        self.assertAlmostEqual(
            result["geri_donusum"],
            result["fire"] * 0.97,
        )
        self.assertAlmostEqual(result["ergitme"], result["fire"] * 0.03)
        self.assertAlmostEqual(
            result["fason"],
            result["geri_donusum"] * 0.25 * self.inputs["usd"],
        )

    def test_energy_consumption_scales_with_production(self) -> None:
        base = self.calculator.hesapla(**self.inputs)
        higher = self.calculator.hesapla(
            **{**self.inputs, "uretim": 300_000}
        )
        for key in (
            "elektrik_tuketim",
            "gaz_tuketim",
            "su_tuketim",
            "enerji_toplam",
            "metal_toplam",
            "fire_toplam",
        ):
            self.assertAlmostEqual(higher[key], base[key] * 1.5)

    def test_default_electricity_coefficient_is_567_kwh_per_ton(self) -> None:
        result = self.calculator.hesapla(**self.inputs)
        self.assertEqual(result["elektrik_kwh_ton"], 567)
        self.assertAlmostEqual(result["elektrik_tuketim"], 113_400)

    def test_elektrik_birim_fiyat_baremi_hesaplanir(self) -> None:
        breakdown = elektrik_birim_fiyat_hesapla(2.40, 0.30, 0.24, 1)
        self.assertAlmostEqual(breakdown["elektrik_alt_toplam"], 2.94)
        self.assertAlmostEqual(
            breakdown["elektrik_birim_fiyat"],
            2.94 * 1.01,
        )
        result = self.calculator.hesapla(
            **{**self.inputs, "elektrik_fiyat": breakdown["elektrik_birim_fiyat"]}
        )
        self.assertAlmostEqual(
            result["elektrik_maliyet"],
            result["elektrik_tuketim"] * breakdown["elektrik_birim_fiyat"],
        )

    def test_maliyet_ana_has_15_usd_items_and_correct_unit_total(self) -> None:
        result = self.calculator.hesapla(**self.inputs)

        self.assertEqual(len(result["maliyet_ana_tl"]), 15)
        self.assertEqual(len(result["maliyet_ana_usd"]), 15)
        self.assertAlmostEqual(
            result["maliyet_ana_toplam_tl"],
            result["donusum_toplam"],
        )
        self.assertAlmostEqual(
            result["maliyet_ana_toplam_usd"],
            result["maliyet_ana_toplam_tl"] / self.inputs["usd"],
        )
        self.assertAlmostEqual(
            result["maliyet_ana_usd_kg_toplam"],
            result["maliyet_ana_toplam_usd"] / self.inputs["uretim"],
        )

    def test_detail_expenses_are_not_reference_scaled(self) -> None:
        base = self.calculator.hesapla(
            **{**self.inputs, "ambalaj": 0}
        )
        lower = self.calculator.hesapla(
            **{**self.inputs, "uretim": 150_000, "ambalaj": 0}
        )
        higher = self.calculator.hesapla(
            **{**self.inputs, "uretim": 300_000, "ambalaj": 0}
        )

        for key in (
            "kalip",
            "sarf",
            "mazot",
            "nakliye",
            "tenefer",
            "kira",
            "amortisman",
            "genel_gider",
        ):
            self.assertAlmostEqual(lower[key], base[key])
            self.assertAlmostEqual(higher[key], base[key])

    def test_factory_unit_costs_are_consistent(self) -> None:
        result = self.calculator.hesapla(**self.inputs)
        self.assertAlmostEqual(
            result["maliyet_ana_usd_kg_toplam"],
            result["maliyet_ana_toplam_tl"]
            / self.inputs["usd"]
            / self.inputs["uretim"],
        )
        self.assertAlmostEqual(
            result["maliyet_ana_usd_ton_toplam"],
            result["maliyet_ana_usd_kg_toplam"] * 1000,
        )

    def test_zero_production_is_rejected(self) -> None:
        invalid_inputs = {**self.inputs, "uretim": 0}
        with self.assertRaisesRegex(ValueError, "Üretim"):
            self.calculator.hesapla(**invalid_inputs)

    def test_negative_cost_is_rejected(self) -> None:
        invalid_inputs = {**self.inputs, "kira": -1}
        with self.assertRaisesRegex(ValueError, "Kira"):
            self.calculator.hesapla(**invalid_inputs)


class PackagingCalculatorTests(unittest.TestCase):
    def test_packaging_items_are_summed(self) -> None:
        result = PackagingCalculator().hesapla(
            strec=10_000,
            naylon=20_000,
            cember=5_000,
            kosebent=2_500,
            etiket=1_500,
        )
        self.assertEqual(result["toplam"], 39_000)

    def test_excel_packaging_reference_values(self) -> None:
        result = PackagingCalculator().excel_hesapla(
            uretim=200_000,
            usd=47.4243,
        )
        self.assertEqual(result["palet_adedi"], 308)
        self.assertAlmostEqual(result["kereste_m3"], 5.56248)
        self.assertAlmostEqual(result["kereste"], 77_874.72)
        self.assertAlmostEqual(result["kosebent"], 7_546)
        self.assertAlmostEqual(result["cember"], 8_624)
        self.assertAlmostEqual(result["strec_adedi"], 168)
        self.assertAlmostEqual(result["strec"], 8_064)

    def test_packaging_scales_reference_items_with_pallets(self) -> None:
        calculator = PackagingCalculator()
        base = calculator.excel_hesapla(200_000, 47.4243)
        higher = calculator.excel_hesapla(300_000, 47.4243)
        lower = calculator.excel_hesapla(150_000, 47.4243)

        self.assertEqual(lower["palet_adedi"], 231)
        self.assertEqual(higher["palet_adedi"], 462)
        self.assertAlmostEqual(lower["strec_adedi"], 126)
        self.assertAlmostEqual(higher["strec_adedi"], 252)
        self.assertAlmostEqual(lower["toplam"], base["toplam"] * 0.75)
        self.assertAlmostEqual(higher["toplam"], base["toplam"] * 1.5)

    def test_stretch_count_scales_directly_with_net_production_and_rounds_up(
        self,
    ) -> None:
        result = PackagingCalculator().excel_hesapla(235_000, 47.4243)

        self.assertEqual(result["strec_adedi"], 198)

    def test_packaging_dimensions_and_rates_are_editable(self) -> None:
        result = PackagingCalculator().excel_hesapla(
            200_000,
            47.4243,
            yansiz_oran=0.60,
            takoz_adet=4,
            kosebent_adet_palet=3,
            cember_mt_palet=20,
            naylon_sarim_orani=0.50,
        )

        self.assertEqual(result["palet_adedi"], 308)
        self.assertAlmostEqual(result["yansiz_palet"], 184.8)
        self.assertEqual(result["kosebent_adedi"], 924)
        self.assertEqual(result["cember_mt"], 6_160)
        self.assertEqual(result["naylon_palet_adedi"], 154)


if __name__ == "__main__":
    unittest.main()
