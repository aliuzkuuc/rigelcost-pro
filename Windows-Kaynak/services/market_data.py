from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from PySide6.QtCore import QObject, QStandardPaths, QUrl, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
)


class MarketDataService(QObject):
    """TCMB kurları ve gecikmeli LME alüminyum verisini asenkron çeker."""

    data_updated = Signal(dict)
    update_failed = Signal(str)
    update_started = Signal()

    TCMB_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
    WESTMETALL_URL = (
        "https://www.westmetall.com/en/markdaten.php?"
        "action=table&field=LME_Al_cash"
    )

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)
        self.pending: set[str] = set()
        self.values: dict[str, Any] = self.load_cache()
        self.errors: list[str] = []

    @staticmethod
    def cache_path() -> Path:
        base = QStandardPaths.writableLocation(
            QStandardPaths.AppDataLocation
        )
        path = Path(base or Path.home() / ".rigelcost")
        return path / "market_cache.json"

    def load_cache(self) -> dict[str, Any]:
        try:
            data = json.loads(self.cache_path().read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {}
        return data if isinstance(data, dict) else {}

    def save_cache(self) -> None:
        temporary: Path | None = None
        try:
            path = self.cache_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(
                json.dumps(self.values, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError:
            # Piyasa verisi ekranda kullanılmaya devam eder; yalnızca kalıcı
            # önbellek yazılamaz.
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def refresh(self) -> None:
        if self.pending:
            return

        self.pending = {"tcmb", "westmetall"}
        self.errors = []
        self.update_started.emit()
        self._request("tcmb", self.TCMB_URL)
        self._request("westmetall", self.WESTMETALL_URL)

    def _request(self, source: str, url: str) -> None:
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"RigelCostPro/4.0.0")
        request.setRawHeader(
            b"Accept",
            b"application/json, application/xml, text/xml, */*",
        )
        request.setTransferTimeout(15_000)
        reply = self.manager.get(request)
        reply.finished.connect(
            lambda source=source, reply=reply: self._finished(source, reply)
        )

    def _finished(self, source: str, reply: QNetworkReply) -> None:
        try:
            if reply.error() != QNetworkReply.NoError:
                raise ValueError(reply.errorString())

            payload = bytes(reply.readAll())
            if source == "tcmb":
                self.values.update(self.parse_tcmb(payload))
            else:
                self.values.update(self.parse_westmetall(payload))
        except (ValueError, KeyError, TypeError, ElementTree.ParseError) as exc:
            readable = "TCMB" if source == "tcmb" else "LME"
            self.errors.append(f"{readable}: {exc}")
        finally:
            reply.deleteLater()
            self.pending.discard(source)

        if self.pending:
            return

        if self.values:
            self.values["updated_at"] = datetime.now().isoformat(
                timespec="seconds"
            )
            self.save_cache()
            self.data_updated.emit(self.values.copy())

        if self.errors:
            self.update_failed.emit(" | ".join(self.errors))

    @staticmethod
    def parse_tcmb(payload: bytes) -> dict[str, Any]:
        root = ElementTree.fromstring(payload)
        rates: dict[str, float] = {}

        for currency in root.findall("Currency"):
            code = currency.attrib.get("CurrencyCode", "")
            if code not in {"USD", "EUR"}:
                continue
            value = currency.findtext("BanknoteSelling")
            if not value:
                raise ValueError(f"{code} efektif satış kuru bulunamadı")
            rates[code.lower()] = float(value.replace(",", "."))

        if "usd" not in rates or "eur" not in rates:
            raise ValueError("USD veya EUR kuru bulunamadı")

        return {
            "usd": rates["usd"],
            "eur": rates["eur"],
            "tcmb_date": root.attrib.get("Date", ""),
            "tcmb_source": "TCMB efektif satış",
        }

    @staticmethod
    def parse_westmetall(payload: bytes) -> dict[str, Any]:
        html = payload.decode("utf-8", errors="replace")
        body_match = re.search(
            r"<tbody[^>]*>\s*<tr[^>]*>(.*?)</tr>",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if body_match is None:
            raise ValueError("LME yedek tablosu bulunamadı")
        cells = re.findall(
            r"<td[^>]*>\s*(.*?)\s*</td>",
            body_match.group(1),
            flags=re.IGNORECASE | re.DOTALL,
        )
        if len(cells) < 2:
            raise ValueError("LME yedek fiyatı bulunamadı")

        date_text = re.sub(r"<[^>]+>", "", cells[0]).strip()
        price_text = re.sub(r"<[^>]+>", "", cells[1]).strip()
        price = float(price_text.replace(",", ""))
        if price <= 0:
            raise ValueError("LME yedek fiyatı geçersiz")
        return {
            "lme": price,
            "lme_date": date_text,
            "lme_source": "Westmetall LME Aluminium Cash-Settlement",
        }
