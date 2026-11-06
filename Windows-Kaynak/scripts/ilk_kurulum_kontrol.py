#!/usr/bin/env python3
"""Sıfır veritabanıyla programın açılışını ve tüm ekranlarını denetler.

Kullanıcı paketi ilk kez açtığında hiçbir veri yoktur. Bu betik o durumu
birebir taklit eder: boş bir veri dizini verir, ana pencereyi kurar ve her
modül/sekme kombinasyonunu gezerek hata alınmadığını doğrular.
"""

from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA_DIR = Path(tempfile.mkdtemp(prefix="rigel_ilk_kurulum_"))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["RIGELCOST_DATA_DIR"] = str(DATA_DIR)

from PySide6.QtWidgets import QApplication  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication([])
    hatalar: list[str] = []

    import main as uygulama  # noqa: E402

    window = uygulama.MainWindow()
    window.resize(1600, 900)
    window.show()
    app.processEvents()

    from pages.workflow import WorkflowPage  # noqa: E402

    sayfalar = window.findChildren(WorkflowPage)
    if not sayfalar:
        print("HATA: Hiç iş akışı sayfası bulunamadı.")
        return 1

    sayfa = sayfalar[0]
    gezilen = 0
    for (bolum, modul), gorunum in sorted(WorkflowPage.CONTEXT_VIEW.items()):
        gezilen += 1
        try:
            sayfa.set_context(bolum, modul)
            app.processEvents()
        except Exception:  # noqa: BLE001
            hatalar.append(
                f"{bolum} / {modul} [{gorunum}]\n{traceback.format_exc()}"
            )

    veritabani = DATA_DIR / "rigel_operations.db"
    print("=" * 68)
    print("İLK KURULUM DENETİMİ (boş veritabanı)")
    print("=" * 68)
    print(f"Veri dizini           : {DATA_DIR}")
    print(f"Veritabanı oluştu     : {'EVET' if veritabani.is_file() else 'HAYIR'}")
    print(f"Ana pencere başlığı   : {window.windowTitle()}")
    print(f"Gezilen sekme         : {gezilen}")
    print(f"Hata sayısı           : {len(hatalar)}")

    if not veritabani.is_file():
        hatalar.append("Veritabanı dosyası oluşturulmadı.")

    for hata in hatalar:
        print("\n" + hata)

    window.close()
    return 1 if hatalar else 0


if __name__ == "__main__":
    raise SystemExit(main())
