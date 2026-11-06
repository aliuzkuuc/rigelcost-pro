from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    kind: str = "text"
    options: tuple[str, ...] = ()
    default: object = ""
    required: bool = False
    readonly: bool = False
    decimals: int = 2


@dataclass(frozen=True)
class ModuleSpec:
    department: str
    name: str
    description: str
    fields: tuple[FieldSpec, ...]
    table_keys: tuple[str, ...]
    prefix: str
    next_step: tuple[str, str] | None = None

    @property
    def field_map(self) -> dict[str, FieldSpec]:
        return {field.key: field for field in self.fields}


def f(
    key: str,
    label: str,
    kind: str = "text",
    *,
    options: Iterable[str] = (),
    default: object = "",
    required: bool = False,
    readonly: bool = False,
    decimals: int = 2,
) -> FieldSpec:
    return FieldSpec(
        key,
        label,
        kind,
        tuple(options),
        default,
        required,
        readonly,
        decimals,
    )


STATUS = ("TASLAK", "BEKLİYOR", "ONAYLANDI", "İŞLEMDE", "TAMAMLANDI", "İPTAL")
ORDER_STATUS = ("AÇIK", "ONAY BEKLİYOR", "ONAYLANDI", "ÜRETİMDE", "HAZIR", "SEVK EDİLDİ", "KAPALI", "İPTAL")
UNITS = ("KG", "TON", "ADET", "METRE", "M²", "M³", "LİTRE", "PAKET")
SURFACES = ("PRES", "ELOKSAL", "BOYALI", "HAM", "DİĞER")
ALLOYS = ("6060", "6060A", "6060B", "6061", "6063", "6063A", "6063B", "6082", "DİĞER")
TEMPERS = ("T4", "T5", "T6", "T66", "DİĞER")

COMMON = (
    f("status", "Durum", "choice", options=STATUS, default="TASLAK", required=True),
    f("description", "Açıklama", "textarea"),
    f("note", "Not", "textarea"),
)

PARTY_FIELDS = (
    f("code", "Cari Kod", required=True),
    f("name", "Firma Adı", required=True),
    f("tax_office", "Vergi Dairesi"),
    f("tax_no", "Vergi No"),
    f("contact", "Yetkili"),
    f("phone", "Telefon"),
    f("email", "E-posta"),
    f("address", "Adres", "textarea"),
    f("city", "Şehir"),
    f("country", "Ülke", default="Türkiye"),
    f("customer", "Müşteri", "bool", default=True),
    f("supplier", "Tedarikçi", "bool"),
    f("subcontractor", "Fasoncu", "bool"),
    f("active", "Aktif", "bool", default=True),
    f("note", "Not", "textarea"),
)

ORDER_FIELDS = (
    f("company", "Firma", required=True),
    f("document_no", "Belge No"),
    f("msp", "MSP"),
    f("order_date", "Sipariş Tarihi", "date"),
    f("delivery_date", "Teslim Tarihi", "date"),
    f("profile_code", "Profil Kod"),
    f("die_code", "Kalıp Kodu"),
    f("stock_name", "Stok Adı", required=True),
    f("length_mm", "Boy (mm)", "number", decimals=0),
    f("unit_weight", "Teorik Ağırlık (kg/m)", "number", decimals=4),
    f("surface", "Yüzey", "choice", options=SURFACES, default="PRES"),
    f("color", "Renk", default="*"),
    f("alloy", "Alaşım", "choice", options=ALLOYS, default="6060B"),
    f("temper", "Sertlik", "choice", options=TEMPERS, default="T5"),
    f("quantity", "Sipariş Adet", "number", decimals=0),
    f("kg", "Teorik Sipariş KG", "number", readonly=True),
    f("unit_price", "Birim Fiyat", "number", decimals=4),
    f("currency", "Döviz", "choice", options=("TL", "USD", "EUR"), default="TL"),
    f("total", "Toplam", "number", readonly=True),
    f("status", "Durum", "choice", options=ORDER_STATUS, default="AÇIK", required=True),
    f("production_approval", "Üretim Onayı", "choice", options=("BEKLİYOR", "KABUL", "RED"), default="BEKLİYOR"),
    f("note", "Not", "textarea"),
)

REQUEST_FIELDS = (
    f("company", "Tedarikçi Firma"),
    f("requester", "Talep Eden"),
    f("request_reason", "Talep Sebebi"),
    f("request_date", "Talep Tarihi", "date"),
    f("delivery_date", "İstenen Teslim Tarihi", "date"),
    f("stock_name", "Malzeme / Hizmet", required=True),
    f("quantity", "Miktar", "number"),
    f("unit", "Birim", "choice", options=UNITS, default="ADET"),
    f("unit_price", "Birim Fiyat", "number", decimals=4),
    f("currency", "Döviz", "choice", options=("TL", "USD", "EUR"), default="TL"),
    f("total", "Toplam", "number", readonly=True),
    f("status", "Durum", "choice", options=STATUS, default="BEKLİYOR"),
    f("note", "Not", "textarea"),
)

STOCK_FIELDS = (
    f("stock_code", "Stok Kod", required=True),
    f("stock_name", "Stok Adı", required=True),
    f("stock_group", "Stok Grup"),
    f("sub_group", "Alt Grup"),
    f("lot_no", "Lot No"),
    f("warehouse", "Ambar"),
    f("quantity", "Gerçek Miktar", "number"),
    f("unit", "Ana Birim", "choice", options=UNITS, default="KG"),
    f("profile_code", "Profil Kodu"),
    f("length_mm", "Boy (mm)", "number", decimals=0),
    f("surface", "Yüzey", "choice", options=SURFACES, default="PRES"),
    f("color", "Renk", default="*"),
    f("alloy", "Alaşım", "choice", options=ALLOYS, default="6060B"),
    f("temper", "Sertlik", "choice", options=TEMPERS, default="T5"),
    f("unit_weight", "Birim Ağırlık (kg/m)", "number", decimals=4),
    f("customer", "Müşteri"),
    f("order_ref", "Sipariş Ref"),
    f("status", "Durum", "choice", options=STATUS, default="TASLAK"),
    f("note", "Not", "textarea"),
)

PROFILE_FIELDS = (
    f("profile_code", "Profil Kodu", required=True),
    f("profile_name", "Profil Adı", required=True),
    f("company", "Profil Firması"),
    f("customer_code", "Müşteri Profil Kodu"),
    f("group", "Profil Grubu"),
    f("unit_weight", "Teorik Ağırlık (kg/m)", "number", decimals=4),
    f("perimeter", "Çevre (mm)", "number"),
    f("surface_quality", "Yüzey Kalitesi"),
    f("alloy", "Alaşım", "choice", options=ALLOYS, default="6060B"),
    f("temper", "Sertlik", "choice", options=TEMPERS, default="T5"),
    f("drawing_path", "PDF Teknik Resim", "file_pdf"),
    f("image_path", "JPG / PNG Profil Görseli", "file_image"),
    f("active", "Aktif", "bool", default=True),
    f("note", "Not", "textarea"),
)

DIE_FIELDS = (
    f("die_code", "Kalıp Kodu", required=True),
    f("profile_code", "Profil Kodu", required=True),
    f("profile_name", "Profil Adı"),
    f("group", "Profil Grubu"),
    f("spare_no", "Yedek No", "integer", default=0),
    f("supplier", "Kalıp Tedarikçisi"),
    f("supplier_code", "Kalıpçı Kodu"),
    f("die_type", "Kalıp Cinsi"),
    f("figure", "Figür", "integer", default=1),
    f("diameter_mm", "Çap (mm)", "number"),
    f("length_mm", "Boy (mm)", "number"),
    f("life_limit_kg", "Ömür Limiti (kg)", "number"),
    f("used_kg", "Basılan KG", "number"),
    f("remaining_kg", "Kalan Ömür (kg)", "number", readonly=True),
    f("usage_pct", "Kullanım %", "number", readonly=True),
    f("tenefer_limit_m", "Tenefer Limiti (m)", "number"),
    f("tenefer_used_m", "Tenefer Kullanım (m)", "number"),
    f("real_weight", "Gerçek Gramaj (kg/m)", "number", decimals=4),
    f("location", "Konum / Raf"),
    f("pdf_path", "PDF Kalıp Dosyası", "file_pdf"),
    f("image_path", "JPG / PNG Kalıp Görseli", "file_image"),
    f(
        "status",
        "Durum",
        "choice",
        options=(
            "AKTİF", "ARŞİVDE", "İMALATTA", "BAKIMDA", "REVİZYON",
            "TEDARİKTE", "HURDA",
        ),
        default="AKTİF",
    ),
    f("active", "Aktif", "bool", default=True),
    f("note", "Not", "textarea"),
)

PRODUCTION_FIELDS = (
    f("company", "Firma", required=True),
    f("order_ref", "Sipariş Ref", required=True),
    f("raw_material", "Hammadde", default="AL. BİLLET 6063B"),
    f("profile_code", "Profil Kod", required=True),
    f("stock_name", "Stok Adı"),
    f("stock_length_mm", "Stok Boy (mm)", "number", decimals=0),
    f("production_length_mm", "Üretim Boy (mm)", "number", decimals=0),
    f("quantity", "Adet", "number", decimals=0),
    f("unit_weight", "Birim Ağırlık (kg/m)", "number", decimals=4),
    f("kg", "KG", "number"),
    f("surface", "Yüzey", "choice", options=SURFACES, default="PRES"),
    f("color", "Renk", default="*"),
    f("alloy", "Alaşım", "choice", options=ALLOYS, default="6060B"),
    f("temper", "Sertlik", "choice", options=TEMPERS, default="T5"),
    f("production_date", "Üretim Tarihi", "date"),
    f("status", "Durum", "choice", options=ORDER_STATUS, default="AÇIK"),
    f("note", "Not", "textarea"),
)

WORK_ORDER_FIELDS = (
    f("production_order_ref", "Üretim Emri No", required=True),
    f("work_order_ref", "İş Emri No"),
    f("order_ref", "Sipariş Ref", required=True),
    f("company", "Firma"),
    f("operation", "Operasyon", "choice", options=("EKSTRÜZYON", "TERMİK GİRİŞ", "TERMİK ÇIKIŞ", "ELOKSAL", "BOYA", "PAKETLEME"), default="EKSTRÜZYON"),
    f("station", "İstasyon", default="PRES 1"),
    f("profile_code", "Profil Kodu"),
    f("quantity", "İş Emri Adet", "number", decimals=0),
    f("produced_quantity", "Üretilen Adet", "number", decimals=0),
    f("remaining_quantity", "Bekleyen Adet", "number", readonly=True, decimals=0),
    f("kg", "İş Emri KG", "number"),
    f("produced_kg", "Üretilen KG", "number"),
    f("remaining_kg", "Bekleyen KG", "number", readonly=True),
    f("priority", "Öncelik", "integer", default=50),
    f("start_date", "Başlangıç", "datetime"),
    f("end_date", "Bitiş", "datetime"),
    f("status", "Durum", "choice", options=ORDER_STATUS, default="AÇIK"),
    f("note", "Not", "textarea"),
)

PRESS_FIELDS = (
    f("production_type", "Üretim Tipi", "choice", options=("PLANLI ÜRETİM", "PLANSIZ ÜRETİM", "TEST", "GERİ ALIM", "GEÇMİŞ VERİ", "KISA BOY", "NUMUNE"), default="PLANLI ÜRETİM"),
    f("press_status", "Pres Durum", "choice", options=("BEKLİYOR", "ÜRETİLİYOR", "TAMAMLANDI", "İPTAL"), default="BEKLİYOR"),
    f("saw_status", "Testere Durum", "choice", options=("BEKLİYOR", "ÜRETİLİYOR", "TAMAMLANDI", "İPTAL"), default="BEKLİYOR"),
    f("station", "İstasyon", default="PRES 1"),
    f("operator", "Operatör"),
    f("shift", "Vardiya", "choice", options=("1.VARDİYA", "2.VARDİYA", "3.VARDİYA"), default="1.VARDİYA"),
    f("order_ref", "Sipariş Ref", required=True),
    f("work_order_ref", "İş Emri No", required=True),
    f("company", "Müşteri"),
    f("profile_code", "Profil Kodu", required=True),
    f("die_code", "Kalıp Kodu"),
    f("spare_no", "Yedek No", "integer", default=0),
    f("figure", "Figür", "integer", default=1),
    f("real_weight", "Reel Gramaj (kg/m)", "number", decimals=4),
    f("theoretical_weight", "Teorik Gramaj (kg/m)", "number", decimals=4),
    f("start_at", "Başlangıç", "datetime"),
    f("end_at", "Bitiş", "datetime"),
    f("duration_min", "Üretim Süresi (dk)", "number"),
    f("die_setup_min", "Kalıp Hazırlık (dk)", "number"),
    f("raw_material", "Hammadde Stok"),
    f("lot_no", "Lot No"),
    f("billet_count", "Billet Adet", "integer"),
    f("metre", "Net Metre", "number"),
    f("gross_kg", "Brüt KG", "number"),
    f("net_kg", "Net KG", "number"),
    f("theoretical_net_kg", "Teorik Net KG", "number", readonly=True),
    f("fire_kg", "Fire KG", "number", readonly=True),
    f("fire_pct", "Fire %", "number", readonly=True),
    f("kg_hour", "KG/Saat", "number", readonly=True),
    f("weight_diff_pct", "Gramaj Fark %", "number", readonly=True),
    f("tenefer_m", "Tenefer Kullanım (m)", "number", readonly=True),
    f("test_ok", "Test Başarılı", "bool"),
    f("note", "Not", "textarea"),
)

PACKING_FIELDS = (
    f("company", "Firma", required=True),
    f("package_no", "Paket No", required=True),
    f("profile_code", "Profil Kodu"),
    f("stock_name", "Stok Adı", required=True),
    f("order_ref", "Sipariş Ref", required=True),
    f("net_kg", "Net KG", "number"),
    f("gross_kg", "Brüt KG", "number"),
    f("package_count", "Paket Adet", "integer", default=1),
    f("quantity", "Adet", "number", decimals=0),
    f("kg", "KG", "number"),
    f("delivery_week", "Teslim Haftası", "integer"),
    f("branch", "Şube", default="FABRİKA"),
    f("warehouse", "Ambar", default="SEVK ÖN"),
    f("surface", "Yüzey", "choice", options=SURFACES, default="PRES"),
    f("color", "Renk", default="*"),
    f("alloy", "Alaşım", "choice", options=ALLOYS, default="6060B"),
    f("temper", "Sertlik", "choice", options=TEMPERS, default="T5"),
    f("packing_date", "Kasalama Tarihi", "date"),
    f("status", "Durum", "choice", options=("KASALANIYOR", "HAZIR", "SEVK EDİLDİ", "İPTAL"), default="KASALANIYOR"),
    f("note", "Not", "textarea"),
)

MAINTENANCE_FIELDS = (
    f("maintenance_type", "Bakım Tipi", "choice", options=("PERİYODİK", "ARIZİ", "ÖNLEYİCİ"), default="PERİYODİK"),
    f("name", "Bakım Adı", required=True),
    f("operation", "Operasyon"),
    f("station", "İstasyon"),
    f("station_section", "İstasyon Bölümü"),
    f("planned_start", "Planlanan Başlangıç", "datetime"),
    f("planned_end", "Planlanan Bitiş", "datetime"),
    f("actual_start", "Gerçekleşen Başlangıç", "datetime"),
    f("actual_end", "Gerçekleşen Bitiş", "datetime"),
    f("downtime_min", "Duruş (dk)", "number", readonly=True),
    f("compliance_pct", "Bakım Uyum %", "number", readonly=True),
    f("status", "Durum", "choice", options=("BAKIM BEKLİYOR", "İŞLEME ALINDI", "TAMAMLANDI", "İPTAL"), default="BAKIM BEKLİYOR"),
    f("description", "Açıklama", "textarea"),
    f("note", "Not", "textarea"),
)


def module(
    department: str,
    name: str,
    description: str,
    fields: tuple[FieldSpec, ...],
    table_keys: Iterable[str],
    prefix: str,
    next_step: tuple[str, str] | None = None,
) -> ModuleSpec:
    return ModuleSpec(
        department,
        name,
        description,
        fields,
        tuple(table_keys),
        prefix,
        next_step,
    )


MODULE_SPECS = (
    module("Satış", "Müşteriler", "Müşteri ve cari kartları.", PARTY_FIELDS, ("code", "name", "contact", "phone", "city", "active"), "MUS"),
    module("Satış", "Teklifler", "Maliyet sonucundan müşteriye verilen teklifler.", ORDER_FIELDS, ("company", "document_no", "stock_name", "kg", "total", "currency", "status"), "TEK", ("Satış", "Satış Siparişleri")),
    module("Satış", "Satış Siparişleri", "Onay, termin, miktar ve üretim bağlantılı siparişler.", ORDER_FIELDS, ("company", "order_date", "delivery_date", "profile_code", "kg", "production_approval", "status"), "SIP", ("Üretim", "Üretim Onayı Bekleyen Siparişler")),
    module("Satış", "Satış İrsaliyeleri", "Sevk edilen sipariş ve irsaliye kayıtları.", ORDER_FIELDS, ("company", "document_no", "delivery_date", "stock_name", "kg", "status"), "IRS", ("Satış", "Satış Faturaları")),
    module("Satış", "Satış Faturaları", "Satış faturaları ve sipariş bağlantıları.", ORDER_FIELDS, ("company", "document_no", "order_date", "total", "currency", "status"), "FAT"),
    module("Satış", "Bekleyen Siparişler", "Kapanmamış satış siparişlerinin görünümü.", ORDER_FIELDS, ("company", "delivery_date", "profile_code", "quantity", "kg", "status"), "BSI"),
    module("Satış", "Bekleyen Siparişler Pivot", "Firma ve termin bazlı bekleyen sipariş özeti.", ORDER_FIELDS, ("company", "delivery_date", "quantity", "kg", "status"), "BSP"),
    module("Satış", "Sipariş Detay (Satış)", "Sipariş satırları ve üretim/sevk miktarları.", ORDER_FIELDS, ("company", "profile_code", "length_mm", "quantity", "kg", "status"), "SDT", ("Üretim", "Üretim Siparişleri (Detay)")),
    module("Satış", "Sipariş Detay (Numune)", "Numune sipariş satırları.", ORDER_FIELDS, ("company", "profile_code", "length_mm", "quantity", "kg", "status"), "NUM"),
    module("Satış", "Profil Fiyat Listeleri", "Müşteri ve profil bazlı fiyat listeleri.", ORDER_FIELDS, ("company", "profile_code", "stock_name", "unit_price", "currency", "status"), "PFL"),
    module("Satış", "Satış Stok Hareketleri", "Satış kaynaklı stok giriş ve çıkışları.", STOCK_FIELDS, ("stock_code", "stock_name", "warehouse", "quantity", "unit", "order_ref"), "SSH"),
    module("Satış", "Satış Sevk Miktarları", "Sipariş, üretim ve sevk miktarı karşılaştırması.", ORDER_FIELDS, ("company", "profile_code", "quantity", "kg", "status"), "SSM"),
    module("Satış", "Şikayetler", "Müşteri şikayetleri ve düzeltici faaliyetler.", ORDER_FIELDS, ("company", "document_no", "profile_code", "order_date", "status", "note"), "SIK"),

    module("Satın Alma", "Tedarikçiler", "Tedarikçi, hizmet veren ve fasoncu kartları.", PARTY_FIELDS, ("code", "name", "contact", "phone", "city", "active"), "TED"),
    module("Satın Alma", "Talep Fişleri", "Bölümlerden gelen satın alma talepleri.", REQUEST_FIELDS, ("requester", "stock_name", "quantity", "unit", "request_date", "status"), "TAF", ("Satın Alma", "Bekleyen Talepler")),
    module("Satın Alma", "Bekleyen Talepler", "Henüz siparişe dönüşmeyen talepler.", REQUEST_FIELDS, ("requester", "stock_name", "quantity", "delivery_date", "status"), "BET", ("Satın Alma", "Teklif Karşılaştırma")),
    module("Satın Alma", "Talep Detay", "Satın alma talep satırları.", REQUEST_FIELDS, ("requester", "stock_name", "quantity", "unit", "status"), "TAD"),
    module("Satın Alma", "Talep Sebepleri", "Talep sebebi tanımları.", (f("name", "Talep Sebebi", required=True), *COMMON), ("name", "status", "description"), "TAS"),
    module("Satın Alma", "Teklif Karşılaştırma", "Tedarikçi fiyat ve teslimat karşılaştırması.", REQUEST_FIELDS, ("company", "stock_name", "quantity", "unit_price", "currency", "delivery_date"), "TKR", ("Satın Alma", "Satın Alma Siparişleri")),
    module("Satın Alma", "Satın Alma Siparişleri", "Onaylanan tedarikçi siparişleri.", REQUEST_FIELDS, ("company", "stock_name", "quantity", "total", "currency", "delivery_date", "status"), "SAS", ("Satın Alma", "Satın Alma İrsaliyeleri")),
    module("Satın Alma", "Satın Alma İrsaliyeleri", "Mal kabul ve irsaliye kayıtları.", REQUEST_FIELDS, ("company", "stock_name", "quantity", "unit", "delivery_date", "status"), "SAI", ("Satın Alma", "Satın Alma Faturaları")),
    module("Satın Alma", "Satın Alma Faturaları", "Tedarikçi faturaları.", REQUEST_FIELDS, ("company", "stock_name", "total", "currency", "request_date", "status"), "SAF"),
    module("Satın Alma", "Bekleyen Siparişler", "Teslim alınmamış satın alma siparişleri.", REQUEST_FIELDS, ("company", "stock_name", "quantity", "delivery_date", "status"), "BSA"),
    module("Satın Alma", "Sipariş Detay", "Satın alma sipariş satırları.", REQUEST_FIELDS, ("company", "stock_name", "quantity", "unit_price", "total", "status"), "SAD"),
    module("Satın Alma", "Satın Alma Stok Hareketleri", "Satın alma kaynaklı stok hareketleri.", STOCK_FIELDS, ("stock_code", "stock_name", "warehouse", "quantity", "unit", "status"), "SAL"),
    module("Satın Alma", "Satın Alma Miktarları", "Sipariş ve teslim miktarı özeti.", REQUEST_FIELDS, ("company", "stock_name", "quantity", "unit", "status"), "SAM"),

    module("Malzeme Yönetimi", "Stok Kartları", "Tüm hammadde, profil, ambalaj ve sarf kartları.", STOCK_FIELDS, ("stock_code", "stock_name", "stock_group", "warehouse", "quantity", "unit", "status"), "STK"),
    module("Malzeme Yönetimi", "Şubeler", "Fabrika ve depo şube tanımları.", PARTY_FIELDS, ("code", "name", "city", "active"), "SUB"),
    module("Malzeme Yönetimi", "Ambarlar", "Şube bağlantılı ambar ve negatif stok politikası.", STOCK_FIELDS, ("stock_code", "stock_name", "warehouse", "status"), "AMB"),
    module("Malzeme Yönetimi", "Müşteri Ürün Kodları", "Müşteri ürün kodu eşleştirmeleri.", STOCK_FIELDS, ("customer", "stock_code", "stock_name", "profile_code", "status"), "MUK"),
    module("Malzeme Yönetimi", "Tedarikçi Ürün Kodları", "Tedarikçi ürün kodu eşleştirmeleri.", STOCK_FIELDS, ("customer", "stock_code", "stock_name", "status"), "TUK"),
    module("Malzeme Yönetimi", "Hizmet Kartları", "Fason ve hizmet kartları.", STOCK_FIELDS, ("stock_code", "stock_name", "stock_group", "unit", "status"), "HZM"),
    module("Malzeme Yönetimi", "Lotlar", "Lot ve izlenebilirlik kayıtları.", STOCK_FIELDS, ("lot_no", "stock_code", "stock_name", "warehouse", "quantity", "order_ref"), "LOT"),
    module("Malzeme Yönetimi", "Stok Fişleri", "Ambar giriş/çıkış ve transfer fişleri.", STOCK_FIELDS, ("stock_code", "stock_name", "warehouse", "quantity", "unit", "order_ref"), "STF"),
    module("Malzeme Yönetimi", "Stok Hareketleri", "Tüm stok hareketlerinin ortak listesi.", STOCK_FIELDS, ("stock_code", "stock_name", "lot_no", "warehouse", "quantity", "unit", "order_ref"), "STH"),
    module("Malzeme Yönetimi", "Birim Setleri", "KG, adet, metre ve paket dönüşümleri.", STOCK_FIELDS, ("stock_code", "stock_name", "unit", "unit_weight", "status"), "BIR"),
    module("Malzeme Yönetimi", "Özellik Setleri", "Yüzey, renk, alaşım ve sertlik setleri.", STOCK_FIELDS, ("stock_group", "surface", "color", "alloy", "temper", "status"), "OZS"),
    module("Malzeme Yönetimi", "Özellikler", "Stok kartlarına atanabilir özellikler.", STOCK_FIELDS, ("stock_code", "stock_name", "surface", "color", "alloy", "temper"), "OZL"),
    module("Malzeme Yönetimi", "Fasoncular", "Fason işçilik tedarikçileri.", PARTY_FIELDS, ("code", "name", "contact", "phone", "active"), "FSN"),
    module("Malzeme Yönetimi", "Kritik Stoklar", "Minimum seviyeye yaklaşan stoklar.", STOCK_FIELDS, ("stock_code", "stock_name", "warehouse", "quantity", "unit", "status"), "KRS"),
    module("Malzeme Yönetimi", "Negatif Stoklar", "Kontrol edilmesi gereken negatif stoklar.", STOCK_FIELDS, ("stock_code", "stock_name", "warehouse", "quantity", "unit", "status"), "NGS"),

    module("Kalıphane", "Profil Kartları", "Profil teknik kartı ve çizim bağlantıları.", PROFILE_FIELDS, ("profile_code", "profile_name", "company", "unit_weight", "alloy", "temper", "active"), "PRF"),
    module("Kalıphane", "Profil Katalog", "Profil resimleri ve katalog görünümü.", PROFILE_FIELDS, ("profile_code", "profile_name", "company", "unit_weight", "drawing_path"), "PKT"),
    module("Kalıphane", "Kalıp Kartları", "Her profilin yedek numaralı kalıp kartları.", DIE_FIELDS, ("die_code", "profile_code", "spare_no", "supplier", "used_kg", "remaining_kg", "status"), "KLP"),
    module("Kalıphane", "İmalattaki Kalıplar", "Kalıp tedarik ve imalat takibi.", DIE_FIELDS, ("die_code", "profile_code", "supplier", "status", "note"), "IMK"),
    module("Kalıphane", "Hurda Kalıplar", "Kullanım dışı kalıp kayıtları.", DIE_FIELDS, ("die_code", "profile_code", "used_kg", "status", "note"), "HUK"),
    module("Kalıphane", "Kalıp Hareketleri", "Kalıp konum, üretim ve bakım hareketleri.", DIE_FIELDS, ("die_code", "profile_code", "location", "used_kg", "status"), "KHA"),
    module("Kalıphane", "Teneferi Yaklaşanlar", "Tenefer sınırına yaklaşan kalıplar.", DIE_FIELDS, ("die_code", "profile_code", "tenefer_used_m", "tenefer_limit_m", "status"), "TEN"),
    module("Kalıphane", "Kalıp Talepleri", "Yeni kalıp ve revizyon talepleri.", DIE_FIELDS, ("profile_code", "supplier", "figure", "status", "note"), "KTA", ("Kalıphane", "Kalıp İş Emirleri")),
    module("Kalıphane", "Kalıp İş Emirleri", "Bakım, tamir ve revizyon iş emirleri.", DIE_FIELDS, ("die_code", "profile_code", "supplier", "status", "note"), "KIE"),
    module("Kalıphane", "Bekleyen İş Emirleri", "Açık kalıp iş emirleri.", DIE_FIELDS, ("die_code", "profile_code", "supplier", "status"), "BKI"),
    module("Kalıphane", "Kalıp Fişleri", "Kalıp işlem ve bakım fişleri.", DIE_FIELDS, ("die_code", "profile_code", "used_kg", "location", "status"), "KFI"),
    module("Kalıphane", "Kalıp Problemleri", "Üretimde görülen kalıp problemleri.", DIE_FIELDS, ("die_code", "profile_code", "status", "note"), "KPR"),
    module("Kalıphane", "Kalıp Verilmeyenler", "İş emrine kalıp atanmamış profiller.", DIE_FIELDS, ("profile_code", "die_code", "status", "note"), "KVE"),
    module("Kalıphane", "Tedarik Bekleyen Kalıplar", "Tedarikçiden beklenen kalıplar.", DIE_FIELDS, ("die_code", "profile_code", "supplier", "status"), "TBK"),

    module("Üretim", "Üretim Siparişleri", "Satış siparişlerinin üretim görünümü.", ORDER_FIELDS, ("company", "delivery_date", "profile_code", "kg", "production_approval", "status"), "URS"),
    module("Üretim", "Üretim Siparişleri (Detay)", "Sipariş satırlarının üretim miktarları.", ORDER_FIELDS, ("company", "profile_code", "length_mm", "quantity", "kg", "status"), "URD"),
    module("Üretim", "Üretim Onayı Bekleyen Siparişler", "Üretim onayı bekleyen satış siparişleri.", ORDER_FIELDS, ("company", "delivery_date", "profile_code", "kg", "production_approval", "status"), "UOB", ("Üretim", "Üretim Planlama")),
    module("Üretim", "Stok Miktarları", "Firma, yüzey ve ambar bazlı üretim stoğu.", STOCK_FIELDS, ("customer", "warehouse", "surface", "quantity", "unit", "profile_code"), "UMI"),
    module("Üretim", "Üretim Planlama", "Siparişlerin üretim ve iş emri planı.", PRODUCTION_FIELDS, ("company", "order_ref", "profile_code", "quantity", "kg", "production_date", "status"), "UPL", ("Üretim", "Üretim Emirleri")),
    module("Üretim", "Planlama Takvimi", "Operasyon ve istasyon bazlı zaman planı.", WORK_ORDER_FIELDS, ("operation", "station", "start_date", "end_date", "priority", "status"), "PTK"),
    module("Üretim", "Reçeteler", "Profilin operasyon rotası ve üretim özellikleri.", PRODUCTION_FIELDS, ("profile_code", "stock_name", "production_length_mm", "surface", "alloy", "temper", "status"), "REC"),
    module("Üretim", "Üretim Emirleri", "Sipariş bazlı hammadde ve üretim emri.", PRODUCTION_FIELDS, ("company", "order_ref", "raw_material", "profile_code", "quantity", "kg", "status"), "UEM", ("Üretim", "İş Emirleri")),
    module("Üretim", "İş Emirleri", "Rota operasyonları ve istasyon iş emirleri.", WORK_ORDER_FIELDS, ("production_order_ref", "order_ref", "operation", "station", "kg", "remaining_kg", "status"), "IEM", ("Üretim", "İstasyon Yükleri")),
    module("Üretim", "İş Emri Miktarları", "İş emri, üretilen ve bekleyen miktar özeti.", WORK_ORDER_FIELDS, ("company", "operation", "station", "quantity", "produced_quantity", "remaining_quantity", "kg", "remaining_kg"), "IMM"),
    module("Üretim", "İstasyon Yükleri", "İstasyon sırası, öncelik ve bekleyen üretim.", WORK_ORDER_FIELDS, ("priority", "profile_code", "work_order_ref", "order_ref", "company", "kg", "remaining_kg"), "ISY", ("Üretim", "Pres Üretim Fişleri")),
    module("Üretim", "Ambar Yükleri", "Üretim ambarındaki lot ve profil stokları.", STOCK_FIELDS, ("lot_no", "stock_code", "stock_name", "warehouse", "quantity", "profile_code", "order_ref"), "UAY"),
    module("Üretim", "Üretim Fişleri", "Üretimin stok giriş, çıkış ve transfer fişleri.", STOCK_FIELDS, ("stock_code", "stock_name", "warehouse", "quantity", "unit", "order_ref", "status"), "UFI"),
    module("Üretim", "Stok Hareketleri", "Üretim kaynaklı tüm stok hareketleri.", STOCK_FIELDS, ("lot_no", "stock_code", "stock_name", "warehouse", "quantity", "unit", "order_ref"), "USH"),
    module("Üretim", "Pres Üretim Fişleri", "Pres, testere, billet, fire ve verimlilik kaydı.", PRESS_FIELDS, ("press_status", "station", "operator", "order_ref", "profile_code", "gross_kg", "net_kg", "fire_pct"), "PUS", ("Üretim", "Pres-Testere Takip")),
    module("Üretim", "Pres Üretim Miktarları", "Pres üretim miktarı ve performans özeti.", PRESS_FIELDS, ("station", "metre", "net_kg", "theoretical_net_kg", "gross_kg", "fire_kg", "kg_hour"), "PUM"),
    module("Üretim", "Pres-Testere Takip", "Pres ve testere tamamlanma durumları.", PRESS_FIELDS, ("press_status", "saw_status", "station", "order_ref", "work_order_ref", "profile_code", "net_kg"), "PTT", ("Üretim", "Eloksal Fişleri")),
    module("Üretim", "Eloksal Fişleri", "Askı, renk, sökme ve hurda miktarları.", PRESS_FIELDS, ("order_ref", "work_order_ref", "company", "profile_code", "net_kg", "fire_kg", "press_status"), "ELF", ("Üretim", "Eloksal Takip")),
    module("Üretim", "Eloksal Takip", "Askılama ve sökme tamamlanma takibi.", PRESS_FIELDS, ("order_ref", "work_order_ref", "company", "profile_code", "net_kg", "press_status"), "ELT", ("Sevkiyat", "Kasalama Fişleri")),
    module("Üretim", "Duruşlar", "Fabrika ve istasyon duruş kayıtları.", MAINTENANCE_FIELDS, ("name", "operation", "station", "actual_start", "actual_end", "downtime_min", "status"), "DRS"),

    module("Sevkiyat", "Kasalama Fişleri", "Firma bazlı kasalama üst fişleri.", PACKING_FIELDS, ("company", "package_no", "packing_date", "warehouse", "net_kg", "gross_kg", "status"), "KAS", ("Sevkiyat", "Kasalama Fişleri (Detay)")),
    module("Sevkiyat", "Kasalama Fişleri (Detay)", "Paket ve sipariş satırı detayları.", PACKING_FIELDS, ("company", "package_no", "stock_name", "net_kg", "gross_kg", "quantity", "order_ref"), "KDT", ("Sevkiyat", "Hazır Kasalar")),
    module("Sevkiyat", "Hazır Kasalar", "Sevke hazır paket ve kasalar.", PACKING_FIELDS, ("company", "package_no", "profile_code", "net_kg", "gross_kg", "delivery_week", "status"), "HAZ", ("Sevkiyat", "Çeki Listeleri")),
    module("Sevkiyat", "Çeki Listeleri", "Siparişleri araç ve sevk belgesinde birleştirir.", PACKING_FIELDS, ("company", "package_no", "order_ref", "net_kg", "gross_kg", "warehouse", "status"), "CEK"),
    module("Sevkiyat", "Ambar Yükleri", "Sevk ön ve sevk hazır ambar yükleri.", STOCK_FIELDS, ("lot_no", "stock_code", "stock_name", "warehouse", "quantity", "profile_code", "order_ref"), "SAY"),

    module("Bakım", "Bakım Talimatları", "Periyodik, arızi ve önleyici bakım talimatları.", MAINTENANCE_FIELDS, ("maintenance_type", "name", "operation", "station", "status"), "BTL", ("Bakım", "Bakım Emirleri")),
    module("Bakım", "Bakım Emirleri", "Planlanan ve gerçekleşen bakım iş emirleri.", MAINTENANCE_FIELDS, ("maintenance_type", "name", "station", "planned_start", "actual_end", "compliance_pct", "status"), "BEM"),
    module("Bakım", "Bakım Bekleyenler", "Henüz tamamlanmamış bakım emirleri.", MAINTENANCE_FIELDS, ("maintenance_type", "name", "operation", "station", "planned_start", "status"), "BBK"),
)


MODULE_INDEX = {(spec.department, spec.name): spec for spec in MODULE_SPECS}
DEPARTMENT_MODULES: dict[str, tuple[str, ...]] = {}
for _spec in MODULE_SPECS:
    DEPARTMENT_MODULES.setdefault(_spec.department, ())
    DEPARTMENT_MODULES[_spec.department] += (_spec.name,)


def get_module_spec(department: str, module_name: str) -> ModuleSpec:
    try:
        return MODULE_INDEX[(department, module_name)]
    except KeyError as exc:
        raise KeyError(f"Bilinmeyen ERP modülü: {department} / {module_name}") from exc
