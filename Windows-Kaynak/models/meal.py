class MealCalculator:

    def hesapla(
        self,
        personel_sayisi,
        gunluk_ucret,
        gun_sayisi,
    ):

        return (
            personel_sayisi
            * gunluk_ucret
            * gun_sayisi
        )