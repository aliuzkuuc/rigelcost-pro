#!/usr/bin/env python3
"""Pres üretim ekranını örnek veriyle doldurup görüntüsünü alır."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from scripts.e2e_pres_fisi import BASKETS, BILLETS, SCRAPS, kur  # noqa: E402
from services.local_workflow import LocalWorkflowService  # noqa: E402
from ui.press_production_dialog import PressProductionDialog  # noqa: E402


def main() -> int:
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as tmp:
        service = LocalWorkflowService(Path(tmp) / "rigel_operations.db")
        work_order_id = kur(service)
        context = service.press_entry_context(work_order_id)
        context["id"] = work_order_id

        dialog = PressProductionDialog(
            context, username="PRES", slip_no=service.peek_next_no("PF")
        )
        dialog.billet_grid.set_rows(BILLETS)
        dialog.basket_grid.set_rows(BASKETS)
        dialog.scrap_grid.set_rows(SCRAPS)
        dialog.qc_username.setText("KK")
        dialog.test_result.setCurrentText("BAŞARILI")
        dialog.die_problem.setCurrentText("GÖRÜNTÜ BOZUK")
        dialog.die_problem_note.setText("3 VE 4 NO ALTTA - VAR 4 FİGÜRDE ÇATI KAYIK")
        dialog.lot.setText("6612")
        dialog.shift.setCurrentText("2.VARDİYA")
        dialog.resize(1500, 940)
        dialog.show()
        for _ in range(3):
            app.processEvents()

        out = Path("/tmp/rigel_pres")
        out.mkdir(exist_ok=True)
        target = out / "ekran_pres.png"
        dialog.grab().save(str(target))
        print(f"Ekran: {target}  ({dialog.width()}x{dialog.height()})")

        # Etiket ve alanın üst üste binmediğini geometriden doğrula.
        cakisma = []
        for label, editor in (
            ("OPERATÖR", dialog.operator),
            ("KK KULLANICISI", dialog.qc_username),
            ("VARDİYA", dialog.shift),
            ("TENEFER NO", dialog.tenefer_no),
            ("ÇIKAN BOY", dialog.result_length),
            ("TEST SONUCU", dialog.test_result),
        ):
            rect = editor.geometry()
            if rect.height() < 20 or rect.width() < 40:
                cakisma.append(f"{label}: {rect.width()}x{rect.height()}")
        if cakisma:
            print("EZİLEN ALANLAR: " + ", ".join(cakisma))
        else:
            print("Tüm giriş alanları tam yükseklikte.")
        return 1 if cakisma else 0


if __name__ == "__main__":
    raise SystemExit(main())
