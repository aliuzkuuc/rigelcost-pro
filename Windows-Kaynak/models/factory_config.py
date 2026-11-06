from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_RIGEL_CONFIG = Path.home() / ".rigelcost" / "rigel.config"


@dataclass(frozen=True)
class FactoryConfig:
    """rigel.config appSettings — fabrika sabitleri."""

    yuzey_id: int = 30
    renk_id: int = 31
    sertlik_id: int = 32
    alasim_id: int = 33
    mekanik_id: int = 34
    pres_yuzey_id: int = 105
    renk_pres_id: int = 110
    renk_pres_ad: str = "*"
    renk_pres_kod: str = "P"
    pres_ad: str = "PRES"
    pres_kod: str = "P"
    termik_on_ambari: int = 5
    termiksiz_id: int = 132
    onay_kabul_id: int = 3
    onay_analiz_id: int = 2
    onay_revizyon_id: int = 5
    onay_iptal_id: int = 6
    tenefer_uyari_metre: int = 500
    paylasim_path: str = ""
    kg_id: int = 1
    adet_id: int = 2
    metre_id: int = 3
    mamul_stok_tur_id: int = 1
    yarimamul_stok_tur_id: int = 2
    kalip_stok_tur_id: int = 4
    mekanik_ad: str = "YOK"
    mekanik_kod: str = "005"

    @classmethod
    def load(cls, path: str | Path | None = None) -> FactoryConfig:
        config_path = Path(path) if path else DEFAULT_RIGEL_CONFIG
        if not config_path.is_file():
            return cls()
        root = ET.parse(config_path).getroot()
        values: dict[str, str] = {}
        for node in root.findall(".//add"):
            key = node.attrib.get("key")
            if key:
                values[key] = node.attrib.get("value", "")

        def int_val(key: str, default: int) -> int:
            try:
                return int(values.get(key, default))
            except (TypeError, ValueError):
                return default

        return cls(
            yuzey_id=int_val("YuzeyId", 30),
            renk_id=int_val("RenkId", 31),
            sertlik_id=int_val("SertlikId", 32),
            alasim_id=int_val("AlasimId", 33),
            mekanik_id=int_val("MekanikId", 34),
            pres_yuzey_id=int_val("PresYuzeyId", 105),
            renk_pres_id=int_val("RenkPresId", 110),
            renk_pres_ad=str(values.get("RenkPresAd", "*")),
            renk_pres_kod=str(values.get("RenkPresKod", "P")),
            pres_ad=str(values.get("PresAd", "PRES")),
            pres_kod=str(values.get("PresKod", "P")),
            termik_on_ambari=int_val("TermikOnAmbari", 5),
            termiksiz_id=int_val("TermiksizId", 132),
            onay_kabul_id=int_val("OnayKabulId", 3),
            onay_analiz_id=int_val("OnayAnalizId", 2),
            onay_revizyon_id=int_val("OnayRevizyonId", 5),
            onay_iptal_id=int_val("OnayIptalId", 6),
            tenefer_uyari_metre=int_val("TeneferUyarıMetre", 500),
            paylasim_path=str(values.get("PaylasimPath", "")),
            kg_id=int_val("KgId", 1),
            adet_id=int_val("AdetId", 2),
            metre_id=int_val("MetreId", 3),
            mamul_stok_tur_id=int_val("MamulStokTurId", 1),
            yarimamul_stok_tur_id=int_val("YarımamulStokTurId", 2),
            kalip_stok_tur_id=int_val("KalipStokTurId", 4),
            mekanik_ad=str(values.get("MekanikAd", "YOK")),
            mekanik_kod=str(values.get("MekanikKod", "005")),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "yuzey_id": self.yuzey_id,
            "renk_id": self.renk_id,
            "pres_yuzey_id": self.pres_yuzey_id,
            "pres_ad": self.pres_ad,
            "termik_on_ambari": self.termik_on_ambari,
            "onay_kabul_id": self.onay_kabul_id,
            "tenefer_uyari_metre": self.tenefer_uyari_metre,
            "paylasim_path": self.paylasim_path,
        }


_FACTORY_CONFIG: FactoryConfig | None = None


def factory_config() -> FactoryConfig:
    global _FACTORY_CONFIG
    if _FACTORY_CONFIG is None:
        _FACTORY_CONFIG = FactoryConfig.load()
    return _FACTORY_CONFIG
