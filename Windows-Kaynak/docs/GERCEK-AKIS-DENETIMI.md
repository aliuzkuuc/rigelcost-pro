# RIGEL Gerçek Akış Denetimi

## Karar

Rigel Cost Pro v4.0.0 içindeki yerel ERP akışı gerçek fabrika kullanımı için
onaylı değildir. Maliyet modülü bu kararın dışındadır ve korunacaktır.

Sorun yalnız arayüz değildir. v4.0.0, RIGEL'daki reçete, rota, planlama,
istasyon, ara ambar ve sevkiyat ilişkilerini fazla sadeleştirmiştir.

## İncelenen gerçek kaynaklar

- RIGEL 1.8.17 kurulum paketi ve gömülü veritabanı geçişleri
- `rigel.config` içindeki kimlik ve ayar anahtarları (şifreli bağlantı bilgisi
  açılmadan)
- Rigel fabrikasından alınmış Üretim, Satış, Sevkiyat, Kalıphane ve Malzeme
  Yönetimi ekran görüntüleri
- `Reçeteler.xlsx`: 2.178 reçete başlığı
- `İş Emirleri.xlsx`: 1.518 iş emri
- `Üretim Emirleri.xlsx`: 506 üretim emri
- `İstasyon Yükleri.xlsx`, `İş Emri Miktarları.xlsx`, `Pres Üretim Listesi.xlsx`
- `Hazır Kasalar.xlsx`, `Kasalama Fişleri.xlsx`, `Kasalama Detay.xlsx` ve
  `Çeki Listeleri.xlsx`
- Rigel fabrikasında eğitim sırasında çekilmiş `1.1.mp4`–`1.11.mp4` videolarının
  tamamı kare kare ve Türkçe konuşma çözümlemesiyle incelendi. Ayrıntılı video
  bulguları `docs/EGITIM-VIDEO-AKISI.md` dosyasındadır.

## RIGEL'daki gerçek temel ayrımlar

### Rota ve reçete aynı kayıt değildir

Rota, operasyonların sırası ve hangi istasyonda çalışacağını belirleyen
şablondur. Rota seçimi yalnız rota adına göre yapılmaz.

Gerçek sistemde aşağıdaki ilişkiler bulunur:

- `ROTA_KOSUL`
- `ROTA_KOSUL_OZELLIK`
- `ROTA_KOSUL_ROTA`
- stok özellikleri (`STOK_TO_OZELLIK`)
- kalıp-istasyon uygunluğu (`KALIP_ISTASYON`)
- sipariş satırının boy, yüzey, renk, alaşım, sertlik ve mekanik değerleri
- askı izi ve boy koşulları
- aynı sipariş satırı için daha önce yapılmış planlama seçimleri

Reçete ise üretilecek stok kartını, seçilen rotayı ve her operasyondaki
malzeme dönüşümünü taşır.

`RECETE_D` satırlarında görülen ana alanlar:

- reçete ve alt reçete kimliği
- operasyon ve istasyon
- işlem tipi
- sıra ve rota sırası
- stok kartı
- miktar ve birim
- ana miktar ve ana birim
- pay ve payda
- ambar
- ekstrüzyon birim ağırlık, kg, adet ve metre değerleri

Bu nedenle reçete yalnız `PRES 1 - TERMİK` metni değildir.

### Siparişten üretime geçiş

Gerçek zincir:

1. Sipariş başlığı oluşturulur.
2. Siparişe birden fazla satır eklenir.
3. Her satırda stok/profil kartı, sipariş boyu, üretim boyu, yüzey, renk,
   alaşım, sertlik, mekanik, adet ve kg bulunur.
4. Satır üretim onayına gider.
5. Uygun reçete ve rota koşullara göre bulunur veya planlamacı tarafından
   seçilir.
6. Planlama, operasyon/istasyon bazında miktar ayırır.
7. Aynı sipariş satırı gerektiğinde birden fazla üretim emrine bölünebilir.
8. Üretim emri hammadde stok kartını da taşır.
9. Reçetenin her operasyonu için ayrı iş emri oluşur.
10. İş emrinde önceki ve sonraki istasyon, planlanan/üretilen/bekleyen adet,
    kg ve metre izlenir.

### Pres ve termik hareketleri

Pres kaydı yalnız iş emrini `tamamlandı` yapmak değildir. Gerçek pres fişinde
en az şu veriler ayrı tutulur:

- üretim tipi
- pres durumu ve testere durumu
- istasyon, operatör ve vardiya
- sipariş ve iş emri referansı
- profil ve kalıp/yedek numarası
- reel ve teorik gramaj
- başlangıç/bitiş zamanı ve süreler
- hammadde stok ve lot numarası
- brüt kg, net kg, fire kg ve fire yüzdesi
- çıkan boy, adet, metre ve kg/saat
- billet adedi ve billet boyları
- tenefer bilgisi ve kalıp problem bilgisi

Termik giriş ve termik çıkış ayrı operasyon/iş emri olarak izlenir. Bir önceki
işlem tamamlanmadan sonraki iş emri istasyon yüküne hazır iş olarak düşmez.

### Ambar ve sevkiyat zinciri

Gerçek Rigel verisinde paketleme/kasalama sonrası paket `SEVK ÖN` ambarındadır.
`Hazır Kasalar.xlsx` içindeki kayıtlar bunu doğrular.

Çeki listesi hazırlandığında seçilen paketler `SEVK HAZIR` aşamasına geçer.
İrsaliye/sevk çıkışı bundan sonra yapılır.

Doğru zincir:

`Üretim mamulü -> SEVK ÖN -> Kasalama/Paket -> Çeki listesi -> SEVK HAZIR -> İrsaliye/Sevk`

## v4.0.0 içindeki kesin uyumsuzluklar

1. `routes` tablosu rota ile reçeteyi aynı kayda indirgiyor.
2. `route_steps`, reçete satırının girdi/çıktı stoklarını, birimini, oranını,
   alt reçetesini ve ambarını taşımıyor.
3. RIGEL aktarımı `RECETE_D` içinden yalnız ilk satırı alıyor.
4. Aktarımda rota bulunamazsa varsayılan `PRES 1 - TERMİK` üretiliyor.
5. Aktarım rota metnini tireden bölerek operasyon tahmin ediyor.
6. Her reçeteye kendiliğinden paketleme adımı ekleniyor.
7. `production_orders.sales_order_line_id UNIQUE` olduğu için bir sipariş
   satırı birden fazla üretim emrine bölünemiyor.
8. Bütün iş emirlerine siparişin aynı adet/kg değeri kopyalanıyor; reçete
   oranları kullanılmıyor.
9. Operasyon tamamlanınca gerekli ara stok giriş/çıkışları yapılmıyor; yalnız
   son adımda tek mamul girişi yazılıyor.
10. Rota koşulları ve kalıp-istasyon uygunluğu uygulanmıyor.
11. Pres ve testere durumları ayrı bir süreç olarak yönetilmiyor.
12. Paket doğrudan `SEVK HAZIR` ambarına taşınıyor. Gerçekte önce `SEVK ÖN`
    aşamasında kalmalıdır.
13. Çeki listesi/SEVK HAZIR transfer aşaması bulunmuyor.

## 4 Ağustos video uyum düzeltme durumu

- `RECETE_D` artık yalnız ilk satırdan ibaret sayılmıyor; bütün reçete satırları
  ayrı `recipe_lines` kayıtları olarak saklanıyor.
- SQL kaynağından gelen gerçek rota adımları korunuyor; rota mevcutsa eksik
  operasyon veya paketleme adımı uydurulmuyor.
- `ROTA_KOSUL`, `ROTA_KOSUL_OZELLIK` ve `ROTA_KOSUL_ROTA` ilişkileri kayıpsız
  saklanıyor.
- Operasyon ve istasyon kimlikleri aktarım sırasında ayrı kartlar olarak
  korunuyor.
- Paket/kasa önce `SEVK ÖN` durumunda oluşuyor.
- Yeni çeki listesi kaydı paketi `SEVK ÖN` ambarından `SEVK HAZIR` ambarına
  hareket ettiriyor.
- Çeki listesine alınmamış paket sevk edilemiyor.
- Termik giriş ve termik çıkış ayrı operasyon olarak oluşturuluyor.
- Her üretim fişi ara ambar giriş/çıkış hareketlerini aynı sipariş, iş emri ve
  lot kimliğiyle yazıyor.
- Sonraki istasyon önceki istasyondan çıkmış kullanılabilir kilogramı aşamıyor.
- Pres fişinde reel/teorik gramaj, billet, sepet, çıkan boy, hazırlık/üretim
  süresi ve eksik nedeni saklanıyor.
- Kalıp bakım/tenefer/konum hareketleri seçere olarak saklanıyor.
- Çeki listesinden satış irsaliyesi ve irsaliyeden birim fiyat veya LME + prim
  faturası üretilebiliyor.
- Tablolara ekran bağlamına göre değişen sağ tık komutları eklendi.

Henüz tamamlanmayan kritik işler: reçete oranlarıyla operasyon miktarı üretmek,
aynı sipariş satırını birden fazla üretim emrine bölmek, kalıp-istasyon
uygunluğunu planlamada zorunlu kılmak, farklı çıkan boy için devam işi açmak ve
rapor/etiket tasarım ekranlarını ürünleştirmek.

## Yeniden uygulama için zorunlu çekirdek tablolar

- operasyonlar
- istasyonlar
- kalıp-istasyon uygunlukları
- özellik tanımları, özellik değerleri ve stok özellikleri
- rotalar ve rota adımları
- rota koşulları ve koşul özellikleri
- reçeteler
- reçete operasyon/malzeme satırları
- planlama başlığı ve operasyon bazlı planlama miktarları
- üretim emirleri (bir sipariş satırına birden fazla olabilir)
- iş emirleri
- iş emri miktarları
- üretim fişleri ve üretim fişi malzeme hareketleri
- lot/ambar bakiyeleri
- kasalama fişleri ve paket satırları
- çeki listeleri ve çeki listesi paketleri
- sevk/irsaliye kayıtları

## Kabul testi

Yeni çekirdek, gerçek veriden seçilecek tek bir sipariş satırında şu sonuçları
aynı anda vermeden Windows paketi hazırlanmayacaktır:

1. Sipariş satırına doğru reçete/rota adayları gelmeli.
2. Seçilen reçetenin bütün girdi ve çıktı satırları korunmalı.
3. Üretim emri hammaddeyi ve üretim miktarını doğru taşımalı.
4. Pres, termik giriş ve termik çıkış iş emirleri doğru sırada oluşmalı.
5. İstasyon yükünde yalnız hazır iş görünmeli.
6. Pres brüt/net/fire kaydı lot ve ara ambar hareketi üretmeli.
7. Termik hareketleri önceki miktarı aşamamalı.
8. Mamul önce `SEVK ÖN` ambarında görünmeli.
9. Kasalama ve çeki listesi sonrası paket `SEVK HAZIR` olmalı.
10. Sevk edilen adet/kg sipariş satırına geri yazılmalı.
11. Aynı olay tekrar işlendiğinde çift stok hareketi oluşmamalı.
12. Maliyet modülünün mevcut hesapları ve raporları değişmemeli.
