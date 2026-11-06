from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtPrintSupport import QPrintDialog, QPrintPreviewDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from reports.grid_exporter import export_grid_pdf, grid_html_document


class DocumentPreviewDialog(QDialog):
    """yazdır / PDF önizleme penceresi."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        title: str,
        subtitle: str,
        headers: list[str],
        rows: list[list[str]],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title or "Belge Önizleme")
        self.resize(720, 420)
        self.title = title
        self.subtitle = subtitle
        self.headers = headers
        self.rows = rows
        self._temp_pdf: Path | None = None

        root = QVBoxLayout(self)
        info = QLabel(
            f"{len(rows)} satır — yazdırmadan önce önizleyin veya PDF olarak kaydedin."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        buttons_row = QHBoxLayout()
        preview_btn = QPushButton("YAZDIR ÖNİZLEME")
        pdf_btn = QPushButton("PDF OLUŞTUR")
        open_btn = QPushButton("PDF AÇ")
        buttons_row.addWidget(preview_btn)
        buttons_row.addWidget(pdf_btn)
        buttons_row.addWidget(open_btn)
        buttons_row.addStretch(1)
        root.addLayout(buttons_row)

        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(self.reject)
        root.addWidget(close_box)

        preview_btn.clicked.connect(self.show_print_preview)
        pdf_btn.clicked.connect(self.save_pdf)
        open_btn.clicked.connect(self.open_pdf)

    def _html(self) -> str:
        return grid_html_document(
            headers=self.headers,
            rows=self.rows,
            title=self.title,
            subtitle=self.subtitle,
        )

    def _ensure_pdf(self) -> Path:
        if self._temp_pdf is None or not self._temp_pdf.exists():
            handle = tempfile.NamedTemporaryFile(
                suffix=".pdf", prefix="rigel-preview-", delete=False
            )
            handle.close()
            self._temp_pdf = Path(handle.name)
            export_grid_pdf(
                headers=self.headers,
                rows=self.rows,
                destination=self._temp_pdf,
                title=self.title,
                subtitle=self.subtitle,
                landscape_mode=len(self.headers) > 8,
            )
        return self._temp_pdf

    def show_print_preview(self) -> None:
        from PySide6.QtGui import QTextDocument

        printer = QPrinter(QPrinter.HighResolution)
        document = QTextDocument()
        document.setHtml(self._html())
        preview = QPrintPreviewDialog(printer, self)
        preview.paintRequested.connect(document.print)
        preview.exec()

    def save_pdf(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        default_name = f"{self.title or 'liste'}.pdf".replace("/", "-")
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF kaydet", default_name, "PDF (*.pdf)"
        )
        if not path:
            return
        export_grid_pdf(
            headers=self.headers,
            rows=self.rows,
            destination=path,
            title=self.title,
            subtitle=self.subtitle,
            landscape_mode=len(self.headers) > 8,
        )
        QMessageBox.information(self, "PDF hazır", f"Dosya kaydedildi:\n{path}")

    def open_pdf(self) -> None:
        path = self._ensure_pdf()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def preview_grid_document(
    parent: QWidget | None,
    *,
    title: str,
    subtitle: str,
    headers: list[str],
    rows: list[list[str]],
) -> None:
    dialog = DocumentPreviewDialog(
        parent,
        title=title,
        subtitle=subtitle,
        headers=headers,
        rows=rows,
    )
    dialog.exec()


def print_html_document(parent: QWidget | None, html_content: str) -> None:
    from PySide6.QtGui import QTextDocument

    printer = QPrinter(QPrinter.HighResolution)
    dialog = QPrintDialog(printer, parent)
    if dialog.exec() != QDialog.Accepted:
        return
    document = QTextDocument()
    document.setHtml(html_content)
    document.print(printer)


def preview_html_document(
    parent: QWidget | None,
    *,
    title: str,
    html_content: str,
) -> None:
    """HTML belge önizleme (çeki listesi, irsaliye, etiket, iş emri)."""
    from PySide6.QtGui import QTextDocument

    dialog = QDialog(parent)
    dialog.setWindowTitle(title or "Belge Önizleme")
    dialog.resize(820, 620)
    root = QVBoxLayout(dialog)

    info = QLabel("Yazdırmadan önce önizleyin veya PDF olarak kaydedin.")
    info.setWordWrap(True)
    root.addWidget(info)

    buttons_row = QHBoxLayout()
    preview_btn = QPushButton("YAZDIR ÖNİZLEME")
    pdf_btn = QPushButton("PDF OLUŞTUR")
    open_btn = QPushButton("PDF AÇ")
    buttons_row.addWidget(preview_btn)
    buttons_row.addWidget(pdf_btn)
    buttons_row.addWidget(open_btn)
    buttons_row.addStretch(1)
    root.addLayout(buttons_row)

    close_box = QDialogButtonBox(QDialogButtonBox.Close)
    close_box.rejected.connect(dialog.reject)
    root.addWidget(close_box)

    temp_pdf: Path | None = None

    def ensure_pdf() -> Path:
        nonlocal temp_pdf
        if temp_pdf is None or not temp_pdf.exists():
            handle = tempfile.NamedTemporaryFile(
                suffix=".pdf", prefix="rigel-doc-", delete=False
            )
            handle.close()
            temp_pdf = Path(handle.name)
            document = QTextDocument()
            document.setHtml(html_content)
            from PySide6.QtPrintSupport import QPrinter

            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(str(temp_pdf))
            document.print(printer)
        return temp_pdf

    def show_preview() -> None:
        document = QTextDocument()
        document.setHtml(html_content)
        printer = QPrinter(QPrinter.HighResolution)
        preview = QPrintPreviewDialog(printer, dialog)
        preview.paintRequested.connect(document.print)
        preview.exec()

    def save_pdf() -> None:
        from PySide6.QtWidgets import QFileDialog

        default_name = f"{title or 'belge'}.pdf".replace("/", "-")
        path, _ = QFileDialog.getSaveFileName(
            dialog, "PDF kaydet", default_name, "PDF (*.pdf)"
        )
        if not path:
            return
        document = QTextDocument()
        document.setHtml(html_content)
        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(path)
        document.print(printer)
        QMessageBox.information(dialog, "PDF hazır", f"Dosya kaydedildi:\n{path}")

    def open_pdf() -> None:
        path = ensure_pdf()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    preview_btn.clicked.connect(show_preview)
    pdf_btn.clicked.connect(save_pdf)
    open_btn.clicked.connect(open_pdf)
    dialog.exec()
