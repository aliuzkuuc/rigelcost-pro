from __future__ import annotations

import unittest

from services.market_data import MarketDataService


class MarketParserTests(unittest.TestCase):
    def test_tcmb_xml_parser(self) -> None:
        xml = b"""<?xml version="1.0"?>
        <Tarih_Date Date="30.07.2026">
          <Currency CurrencyCode="USD">
            <ForexSelling>47.4243</ForexSelling>
            <BanknoteSelling>47.4955</BanknoteSelling>
          </Currency>
          <Currency CurrencyCode="EUR">
            <ForexSelling>53.9438</ForexSelling>
            <BanknoteSelling>54.0247</BanknoteSelling>
          </Currency>
        </Tarih_Date>"""
        result = MarketDataService.parse_tcmb(xml)
        self.assertAlmostEqual(result["usd"], 47.4955)
        self.assertAlmostEqual(result["eur"], 54.0247)
        self.assertEqual(result["tcmb_source"], "TCMB efektif satış")

    def test_tcmb_xml_parser_requires_banknote_selling(self) -> None:
        xml = b"""<?xml version="1.0"?>
        <Tarih_Date Date="30.07.2026">
          <Currency CurrencyCode="USD"><ForexSelling>47.4243</ForexSelling></Currency>
          <Currency CurrencyCode="EUR"><ForexSelling>53.9438</ForexSelling></Currency>
        </Tarih_Date>"""
        with self.assertRaisesRegex(ValueError, "efektif satış"):
            MarketDataService.parse_tcmb(xml)

    def test_westmetall_uses_latest_cash_settlement_row(self) -> None:
        payload = b"""
        <table><tbody>
          <tr><td>29. July 2026</td><td>3,207.00</td>
          <td>3,177.00</td><td>267,800</td></tr>
        </tbody></table>
        """
        result = MarketDataService.parse_westmetall(payload)
        self.assertEqual(result["lme"], 3_207)
        self.assertEqual(result["lme_date"], "29. July 2026")


if __name__ == "__main__":
    unittest.main()
