"""Excel / fabrika ERP tarzı sütun filtre satırı — çoklu seçim (checkbox) popup."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# Fabrika ERP: başlık + filtre satırı veri kaydırılırken sabit kalır.
HEADER_HEIGHT = 38
FILTER_ROW_HEIGHT = 26

EMPTY_DISPLAY = "(Boş)"


def normalize_tr(text: object) -> str:
    """Türkçe karakterleri koruyarak büyük/küçük harf duyarsız karşılaştırma."""
    value = str(text or "")
    return (
        value.replace("İ", "i")
        .replace("I", "ı")
        .replace("Ş", "ş")
        .replace("Ğ", "ğ")
        .replace("Ü", "ü")
        .replace("Ö", "ö")
        .replace("Ç", "ç")
        .casefold()
    )


def _display_label(value: str) -> str:
    return EMPTY_DISPLAY if value == "" else value


def _sort_key(value: str) -> tuple[int, str]:
    return (0 if value == "" else 1, normalize_tr(value))


class MultiSelectFilterPopup(QFrame):
    """Excel AutoFilter tarzı popup: arama + Tümünü seç + checkbox listesi."""

    applied = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("columnFilterPopup")
        self.setMinimumWidth(260)
        self.setMaximumHeight(420)
        self._values: list[str] = []
        self._checks: dict[str, QCheckBox] = {}
        self._block = False

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Ara / metin içerir…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search_changed)
        root.addWidget(self.search)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.select_all_btn = QPushButton("Tümünü seç")
        self.select_all_btn.setObjectName("filterPopupAction")
        self.clear_btn = QPushButton("Temizle")
        self.clear_btn.setObjectName("filterPopupAction")
        self.select_all_btn.clicked.connect(self._select_visible)
        self.clear_btn.clicked.connect(self._clear_visible)
        actions.addWidget(self.select_all_btn)
        actions.addWidget(self.clear_btn)
        actions.addStretch(1)
        root.addLayout(actions)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._list_host = QWidget()
        self._list_layout = QVBoxLayout(self._list_host)
        self._list_layout.setContentsMargins(2, 2, 2, 2)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list_host)
        root.addWidget(self._scroll, 1)

        contains_row = QHBoxLayout()
        contains_row.addWidget(QLabel("İçerir:"))
        self.contains = QLineEdit()
        self.contains.setPlaceholderText("serbest metin (opsiyonel)")
        self.contains.setClearButtonEnabled(True)
        contains_row.addWidget(self.contains, 1)
        root.addLayout(contains_row)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.apply_btn = QPushButton("Uygula")
        self.apply_btn.setObjectName("filterPopupApply")
        self.cancel_btn = QPushButton("Kapat")
        self.apply_btn.clicked.connect(self._apply)
        self.cancel_btn.clicked.connect(self.hide)
        footer.addWidget(self.apply_btn)
        footer.addWidget(self.cancel_btn)
        root.addLayout(footer)

    def populate(
        self,
        values: list[str],
        *,
        selected: set[str] | None,
        contains: str = "",
    ) -> None:
        self._block = True
        self._values = list(values)
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._checks.clear()

        active = set(values) if selected is None else set(selected)
        for value in values:
            check = QCheckBox(_display_label(value))
            check.setChecked(value in active)
            check.setProperty("filterValue", value)
            self._checks[value] = check
            self._list_layout.addWidget(check)
        self._list_layout.addStretch(1)

        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.contains.setText(contains)
        self._block = False
        self._filter_list("")

    def selected_values(self) -> set[str]:
        return {value for value, check in self._checks.items() if check.isChecked()}

    def contains_text(self) -> str:
        return self.contains.text().strip()

    def _visible_values(self) -> list[str]:
        needle = normalize_tr(self.search.text().strip())
        result: list[str] = []
        for value, check in self._checks.items():
            label = normalize_tr(_display_label(value))
            if not needle or needle in label:
                result.append(value)
                check.setVisible(True)
            else:
                check.setVisible(False)
        return result

    def _filter_list(self, _text: str = "") -> None:
        self._visible_values()

    def _on_search_changed(self, text: str) -> None:
        self._filter_list(text)

    def _select_visible(self) -> None:
        for value in self._visible_values():
            self._checks[value].setChecked(True)

    def _clear_visible(self) -> None:
        for value in self._visible_values():
            self._checks[value].setChecked(False)

    def _apply(self) -> None:
        self.applied.emit()
        self.hide()


class MultiSelectFilterButton(QToolButton):
    """Sütun filtresi tetikleyici — tıklanınca çoklu seçim popup açar."""

    filterChanged = Signal()

    def __init__(
        self,
        key: str,
        label: str,
        parent: QWidget | None = None,
        *,
        idle_caption: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.key = key
        self.column_label = label
        # Fabrika ERP'sinde filtre satırı sütun adını değil kısa bir işleç
        # simgesini gösterir; sütun adı yalnızca ipucunda kalır.
        self.idle_caption = idle_caption
        self.setObjectName("columnFilterButton")
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)
        # Özel popup kullanıyoruz; InstantPopup boş menü açmasın
        self.setPopupMode(QToolButton.DelayedPopup)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedHeight(24)
        self.setMinimumWidth(40)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setToolTip(
            f"Sütun filtresi (Excel tarzı çoklu seçim): {label}\n"
            "Tıklayın → checkbox listesi, Tümünü seç / Temizle, Uygula"
        )

        self._available: list[str] = []
        # None = tümü seçili (filtre yok); set = yalnızca bu değerler
        self._selected: set[str] | None = None
        self._contains = ""
        self._popup = MultiSelectFilterPopup(self)
        self._popup.applied.connect(self._on_popup_applied)
        self.clicked.connect(self._open_popup)
        self._refresh_caption()

    def available_values(self) -> list[str]:
        return list(self._available)

    def set_available_values(self, values: list[str]) -> None:
        ordered = sorted(set(values), key=_sort_key)
        self._available = ordered
        if self._selected is not None:
            self._selected = {v for v in self._selected if v in self._available}
            if not self._available or self._selected == set(self._available):
                self._selected = None
        self._refresh_caption()

    def selected_values(self) -> set[str] | None:
        return None if self._selected is None else set(self._selected)

    def contains_text(self) -> str:
        return self._contains

    def is_active(self) -> bool:
        return self._selected is not None or bool(self._contains)

    def set_filter(
        self,
        *,
        values: set[str] | None = None,
        contains: str = "",
        emit: bool = True,
    ) -> None:
        """Programatik filtre. values=None → tümü (pasif); set → alt küme."""
        self._contains = (contains or "").strip()
        if values is None:
            self._selected = None
        else:
            chosen = {str(v) for v in values}
            if self._available and chosen >= set(self._available):
                self._selected = None
            else:
                self._selected = chosen
        self._refresh_caption()
        if emit:
            self.filterChanged.emit()

    def clear_filter(self, *, emit: bool = True) -> None:
        self.set_filter(values=None, contains="", emit=emit)

    def _idle_text(self) -> str:
        return self.idle_caption if self.idle_caption else f"{self.column_label}…"

    def _refresh_caption(self) -> None:
        if self._contains and self._selected is None:
            text = f"~{self._contains}"
        elif self._selected is None and not self._contains:
            text = self._idle_text()
        elif self._selected is not None and len(self._selected) == 0:
            text = "(yok)"
        elif self._selected is not None and len(self._selected) == 1:
            only = next(iter(self._selected))
            text = _display_label(only)
        elif self._selected is not None:
            text = f"{len(self._selected)} seçili"
        else:
            text = self._idle_text()
        if self._contains and self._selected is not None:
            text = f"{text}+~"
        self.setText(text)
        self.setProperty("filterActive", "true" if self.is_active() else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def _open_popup(self) -> None:
        if not self._available:
            # Veri henüz yoksa bile boş liste ile aç — contains kullanılabilir
            self._popup.populate([], selected=set(), contains=self._contains)
        else:
            self._popup.populate(
                self._available,
                selected=self._selected,
                contains=self._contains,
            )
        pos = self.mapToGlobal(QPoint(0, self.height()))
        self._popup.move(pos)
        self._popup.resize(max(260, self.width()), 360)
        self._popup.show()
        self._popup.search.setFocus(Qt.PopupFocusReason)

    def _on_popup_applied(self) -> None:
        chosen = self._popup.selected_values()
        contains = self._popup.contains_text()
        if not self._available:
            self.set_filter(values=None, contains=contains, emit=True)
            return
        if chosen == set(self._available) and not contains:
            self.set_filter(values=None, contains="", emit=True)
        elif chosen == set(self._available):
            self.set_filter(values=None, contains=contains, emit=True)
        else:
            self.set_filter(values=chosen, contains=contains, emit=True)


class ColumnFilterBar(QFrame):
    """Başlıkların altında Excel tarzı çoklu seçim filtre satırı.

    Genişlikler ve yatay kaydırma bağlı QTableWidget ile senkron tutulur.
    """

    filtersChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("columnFilterBar")
        self.setFixedHeight(28)
        self._columns: list[tuple[str, str]] = []
        self._editors: list[MultiSelectFilterButton] = []
        self._keys: list[str] = []
        self._table: QTableWidget | None = None
        self._block = False
        self._format_value: Callable[[str, object], str] | None = None
        self._idle_caption: str | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("columnFilterScroll")
        self._scroll.setWidgetResizable(False)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setFixedHeight(26)

        self._inner = QWidget()
        self._inner.setObjectName("columnFilterInner")
        self._row = QHBoxLayout(self._inner)
        self._row.setContentsMargins(0, 1, 0, 1)
        self._row.setSpacing(0)
        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll)

    def set_value_formatter(self, formatter: Callable[[str, object], str]) -> None:
        self._format_value = formatter

    def attach_table(self, table: QTableWidget) -> None:
        if self._table is not None:
            header = self._table.horizontalHeader()
            try:
                header.sectionResized.disconnect(self._on_section_resized)
            except (TypeError, RuntimeError):
                pass
            try:
                self._table.horizontalScrollBar().valueChanged.disconnect(
                    self._on_table_scrolled
                )
            except (TypeError, RuntimeError):
                pass
        self._table = table
        header = table.horizontalHeader()
        header.sectionResized.connect(self._on_section_resized)
        table.horizontalScrollBar().valueChanged.connect(self._on_table_scrolled)
        table.installEventFilter(self)

    def eventFilter(self, watched: object, event: object) -> bool:  # noqa: N802
        from PySide6.QtCore import QEvent

        if watched is self._table and event.type() == QEvent.Resize:
            self.sync_widths()
        return super().eventFilter(watched, event)

    def set_idle_caption(self, caption: str | None) -> None:
        """Filtresiz hücrelerde sütun adı yerine gösterilecek kısa simge."""
        self._idle_caption = caption or None
        for editor in self._editors:
            editor.idle_caption = self._idle_caption
            editor._refresh_caption()

    def configure(
        self,
        columns: list[tuple[str, str]] | tuple[tuple[str, str], ...],
        *,
        preserve: bool = False,
    ) -> None:
        """Sütun anahtar/etiketlerine göre filtre hücrelerini kurar."""
        previous: dict[str, tuple[set[str] | None, str]] = {}
        if preserve:
            for key, editor in zip(self._keys, self._editors):
                previous[key] = (editor.selected_values(), editor.contains_text())

        self._block = True
        while self._row.count():
            item = self._row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._editors.clear()
        self._keys.clear()
        self._columns = list(columns)

        for key, label in self._columns:
            editor = MultiSelectFilterButton(key, label, idle_caption=self._idle_caption)
            editor.filterChanged.connect(self._emit_changed)
            if key in previous:
                values, contains = previous[key]
                editor.set_filter(values=values, contains=contains, emit=False)
            self._row.addWidget(editor)
            self._editors.append(editor)
            self._keys.append(key)

        self._row.addStretch(1)
        self._block = False
        self.sync_widths()
        self._on_table_scrolled(
            self._table.horizontalScrollBar().value() if self._table else 0
        )

    def update_distinct_values(
        self,
        rows: list[dict],
        *,
        format_value: Callable[[str, object], str] | None = None,
    ) -> None:
        """Kaynak satırlardan sütun bazlı benzersiz değerleri günceller."""
        formatter = format_value or self._format_value
        for key, editor in zip(self._keys, self._editors):
            unique: set[str] = set()
            for row in rows:
                raw = row.get(key)
                if formatter is not None:
                    cell = formatter(key, raw)
                else:
                    cell = "" if raw is None else str(raw)
                unique.add(cell)
            editor.set_available_values(sorted(unique, key=_sort_key))

    def editor_for(self, key: str) -> MultiSelectFilterButton | None:
        try:
            return self._editors[self._keys.index(key)]
        except ValueError:
            return None

    def set_column_filter(
        self,
        key: str,
        *,
        values: set[str] | None = None,
        contains: str = "",
        emit: bool = True,
    ) -> None:
        editor = self.editor_for(key)
        if editor is None:
            return
        editor.set_filter(values=values, contains=contains, emit=emit)

    def _emit_changed(self, *_args: object) -> None:
        if not self._block:
            self.filtersChanged.emit()

    def active_filters(self) -> dict[str, set[str] | str]:
        """Aktif filtreler: set → seçili değerler; str → yalnızca metin içerir."""
        result: dict[str, set[str] | str] = {}
        for key, editor in zip(self._keys, self._editors):
            if not editor.is_active():
                continue
            selected = editor.selected_values()
            contains = editor.contains_text()
            if selected is not None:
                result[key] = set(selected)
            elif contains:
                result[key] = contains
        return result

    def has_active_filters(self) -> bool:
        return any(editor.is_active() for editor in self._editors)

    def clear_filters(self) -> None:
        self._block = True
        for editor in self._editors:
            editor.clear_filter(emit=False)
        self._block = False
        self.filtersChanged.emit()

    def sync_widths(self) -> None:
        if self._table is None or not self._editors:
            return
        total = 0
        count = min(len(self._editors), self._table.columnCount())
        for index in range(count):
            width = max(40, self._table.columnWidth(index))
            self._editors[index].setFixedWidth(width)
            total += width
        viewport_w = self._table.viewport().width()
        if total < viewport_w:
            total = viewport_w
        self._inner.setFixedWidth(max(total, 1))
        self._inner.setFixedHeight(24)

    def _on_section_resized(self, _index: int, _old: int, _new: int) -> None:
        self.sync_widths()

    def _on_table_scrolled(self, value: int) -> None:
        self._scroll.horizontalScrollBar().setValue(value)

    def row_matches(
        self,
        row: dict,
        *,
        format_value: Callable[[str, object], str] | None = None,
    ) -> bool:
        """Kayıt satırının aktif sütun filtrelerine uyup uymadığını döner."""
        if not self.has_active_filters():
            return True
        formatter = format_value or self._format_value
        for key, editor in zip(self._keys, self._editors):
            if not editor.is_active():
                continue
            raw = row.get(key)
            if formatter is not None:
                cell = formatter(key, raw)
            else:
                cell = "" if raw is None else str(raw)
            contains = editor.contains_text()
            if contains and normalize_tr(contains) not in normalize_tr(cell):
                return False
            selected = editor.selected_values()
            if selected is not None:
                cell_norm = normalize_tr(cell)
                if not any(cell_norm == normalize_tr(value) for value in selected):
                    return False
        return True


class FilterRowTable(QTableWidget):
    """Sütun başlığının hemen altına sabitlenmiş filtre satırlı tablo.

    Fabrika ERP'sinde filtre satırı başlıkla veri arasında durur. Qt başlığı
    görünümün üst kenarına yapıştırdığı için üst kenar boşluğu başlık + filtre
    kadar büyütülür ve ikisi düzen sonrası elle konumlandırılır.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.horizontalHeader().setFixedHeight(HEADER_HEIGHT)
        self._filter_bar = ColumnFilterBar(self)
        self._filter_bar.setFixedHeight(FILTER_ROW_HEIGHT)
        self._filter_bar.attach_table(self)
        self._filter_bar.raise_()
        self._laying_out = False

    @property
    def filter_bar(self) -> ColumnFilterBar:
        return self._filter_bar

    def _filter_height(self) -> int:
        if self._filter_bar.isHidden():
            return 0
        return FILTER_ROW_HEIGHT

    def updateGeometries(self) -> None:  # noqa: N802 - Qt imzası
        super().updateGeometries()
        if self._laying_out:
            return
        self._laying_out = True
        try:
            bar_height = self._filter_height()
            left = (
                self.verticalHeader().width()
                if self.verticalHeader().isVisible()
                else 0
            )
            frame = self.frameWidth()
            # setViewportMargins yeniden düzen tetikler; koruma bayrağı
            # yüzünden iç çağrı erken döner, konumlandırma burada tamamlanır.
            self.setViewportMargins(left, HEADER_HEIGHT + bar_height, 0, 0)
            width = self.viewport().width()
            self.horizontalHeader().setGeometry(
                frame + left, frame, width, HEADER_HEIGHT
            )
            if bar_height:
                self._filter_bar.setGeometry(
                    frame + left, frame + HEADER_HEIGHT, width, bar_height
                )
                self._filter_bar.raise_()
        finally:
            self._laying_out = False
