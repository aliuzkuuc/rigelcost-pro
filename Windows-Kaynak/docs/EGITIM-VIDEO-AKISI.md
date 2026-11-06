# RIGEL Eğitim Videolarından Doğrulanan Rigel İş Akışı

Bu belge, Rigel fabrikasında RIGEL eğitimi sırasında kaydedilen `1.1.mp4`–
`1.11.mp4` dosyalarının görüntü ve Türkçe konuşma çözümlemesine dayanır. Amaç
arayüzü kopyalamak değil; kullanıcıların üç yıldır kullandığı kayıt ilişkisini
Rigel Cost Pro içinde kendi kodumuz ve kendi veritabanımızla kurmaktır. Maliyet
modülü bu operasyon veritabanından ayrı kalır ve mevcut hesapları korunur.

## Değişmeyen ana kimlik zinciri

```text
Müşteri
  -> Profil kartı
    -> Kalıp / yedek kalıp
      -> Reçete + koşula uygun rota
        -> Satış siparişi ve sipariş satırı
          -> Üretim emri
            -> Sıralı iş emirleri
              -> Pres / termik / yüzey üretim fişleri
                -> Lot ve ara ambar hareketleri
                  -> Paket / kasa
                    -> Çeki listesi
                      -> Satış irsaliyesi / sevkiyat
                        -> Satış faturası
```

Bir ekranda gerçekleşen işlem diğer ekrana metin kopyalamaz. Aynı sipariş
satırının, üretim emrinin, iş emrinin, paketin ve sevk belgesinin kimlikleri
ilişkisel olarak korunur.

## Videolarda görülen doğrulanmış işlevler

### 1.1 — Profil kartları

- Müşteri ve tedarikçi profil kodları bulunur.
- Profil bir veya birden fazla kalıp/yedek kalıpla bağlantılıdır.
- Birleşik profiller için yüzey ve boy bilgisi taşıyan reçete gerekir.
- Satış, planlama ve pres operatörü için ayrı uyarı/notlar görülebilir.
- PDF/JPG doküman ekleme, açma, dışarı aktarma ve silme vardır.
- Sağ tık profil kartı, sipariş hareketi, stok hareketi, stok kartı, kalıp
  amortismanı ve dokümanlara ulaşmanın ana yoludur.

### 1.2–1.3 — Kalıp kartları ve kalıp hareketleri

- Kalıp profil, yedek no, figür, tedarikçi, gerçek ağırlık ve rafla bağlıdır.
- Geçmiş brüt/net, pres bağlantısı, tenefer adedi ve başlangıç tarihi girilir.
- Ömür hem basılan miktar hem tenefer metre/devir bilgisiyle izlenir.
- Bakım, kırık kapak, tenefere gönderme/geliş ve firma hareketleri seçere
  şeklinde saklanır.
- Çoklu kalıp seçilip sağ tıkla toplu hareket girilebilir.
- Operasyon ile istasyon ayrıdır: ekstrüzyon bir operasyon, PRES 1/PRES 2 o
  operasyonun istasyonlarıdır.

### 1.4 — Ambarlar

- Ambar fiziksel malzeme konumudur; operasyon değildir.
- Hammadde, termik ön, sevk ön, sevk hazır, boya/eloksal ön, fason, hurda,
  sarf ve mamul stok ayrı olabilir.
- Ambarlar şubeye bağlıdır. Fabrika ve gelecekteki depo ayrı şube olabilir.
- Negatif stok kontrolü ambar bazında engelle, uyar veya geçici izin şeklinde
  tanımlanabilir.

### 1.5 — Satış siparişi

- Müşteri kartında birden fazla sevk adresi bulunabilir.
- İç sipariş numarası ve müşterinin zorunlu sipariş/belge numarası ayrı tutulur.
- Sipariş başlığı teslim tarihi/yöntemi, döviz ve kuru taşır.
- Her satır profil kartı, kalıp, boy, yüzey, renk, alaşım, sertlik, adet, kg ve
  birim fiyat taşır.
- Profil ve kalıp elle yeniden yazılmaz; mevcut kartlardan seçilir.

### 1.6–1.7 — İstasyon yükü ve pres üretimi

- Pres operatörü yalnız istasyonuna hazır düşen iş emirlerini görür.
- Yetkili kullanıcı sağ tıkla tek veya çoklu iş emri önceliğini ve rengini
  değiştirebilir.
- Genel sipariş notu ile sipariş satırı notu operatör ekranında görünür.
- Önerilen kalıp gelir fakat operatör kullanılan yedeği doğrular.
- Reel gramaj zorunludur; sonraki üretime aktarılır ve tolerans dışıysa uyarır.
- Başlangıç/bitiş, hazırlık süresi, billet boy/adedi, lot/şarj, sepet, çıkan boy,
  eksik adet ve eksik nedeni tutulur.
- Brüt billet ile sepet neti fire/verimliliği oluşturur.
- Kısmi üretimde kalan miktar iş emrinde kalır; fazla üretim uyarılır.
- Siparişten farklı çıkan boy için aynı referansı koruyan devam işi açılabilir.

### 1.8 — Termik ve paketleme

- Termik giriş ile termik çıkış ayrı fiş/işlem olarak kaydedilir.
- Önceki işlem tamamlanmadan sonraki istasyon hazır olmaz.
- Tek veya çoklu satır sağ tıkla operatör üretim fişine alınabilir.
- Son üretim işleminden sonra ürün mamuldür ve Sevk Ön ambarında izlenir.
- Paket/kasa satırında teorik değil, teraziden gelen gerçek net ve brüt kg
  kullanılır. Paket numaraları otomatik üretilir.

### 1.9 — Paket etiketi

- Paketlenen ve kalan miktar birlikte izlenir.
- Gerçek/teorik gramaj farkı için uyarı vardır.
- Etiket şablonları firmaya göre düzenlenebilir; standart şablon kilitlidir,
  kopyası özelleştirilir.
- Tek profilli ve çok profilli paket etiketi farklı içerik taşır.

### 1.10 — Çeki listesi

- Sevke hazır paketler müşteriye göre seçilip çeki listesine bağlanır.
- Çeki listesine bağlanan paket ikinci bir açık çeki listesinde görünmez.
- Liste araç yüklemede kullanılacak paket, profil, sipariş, net/brüt kg ve
  görsel ayrıntılarını yazdırır.
- Sağ tıkla çeki listesinden satış irsaliyesi/sevkiyat oluşturulur.

### 1.11 — İrsaliye, sipariş kapanması ve fatura

- İrsaliye kaydedilince sevk gerçekleşir ve irsaliye numarası çeki listesine
  geri yazılır.
- Sipariş satırında sevk yüzdesi güncellenir; tam miktar sevk edilince satır ve
  sipariş kapanır.
- Sevk formu yazdırılabilir.
- İrsaliye faturaya dönüştürülebilir.
- Fiyat birim fiyat üzerinden veya LME + prim üzerinden iki yönlü
  hesaplanabilir; fatura tarihinin kuru ayrı saklanır.

## Sağ tık davranış standardı

Her tabloda ortak işlemler: görüntüle, kayıt bilgisi, yenile, Excel'e aktar ve
sütunları sıfırla. Bunlara ek olarak ekran bağlamına göre:

- Profil: profil kartı, sipariş/stok hareketleri, dokümanlar.
- Kalıp: kalıp hareketi, üretim geçmişi, başlangıç bilgisi, tenefer ve belgeler.
- Sipariş: üretime onay, sipariş ilerlemesi ve bağlı hareketler.
- İstasyon yükü: operatör fişi, çoklu öncelik değişimi ve üretim geçmişi.
- Paket: çeki listesi oluşturma.
- Çeki listesi: satış irsaliyesi/sevkiyat oluşturma.
- İrsaliye: faturala.

Komutun görünmesi yetkiye bağlıdır; işlem yine servis katmanında durum ve miktar
kontrolünden geçer.

## Uygulanan ilk video uyum paketi

- Termik giriş ve termik çıkış ayrı rota adımlarıdır.
- Paketleme rota iş emri olmaktan çıkarılmış, üretim sonrası ayrı fiş olmuştur.
- Her üretim fişi girdi ambarından çıkış ve çıktı ambarına giriş üretir.
- Sonraki istasyon önceki istasyonun kullanılabilir miktarını aşamaz.
- Pres fişine reel/teorik gramaj, billet, sepet, çıkan boy, süre ve eksik neden
  alanları eklenmiştir.
- Kalıp hareketleri ve konum geçmişi ilişkisel olarak kaydedilir.
- Çeki listesinden yalnız bir kez irsaliye/sevkiyat oluşturulur.
- Sevk edilen miktar sipariş satırına geri yazılır ve sipariş kapanır.
- İrsaliye birim fiyat veya LME + prim yöntemiyle faturaya dönüşür.
- Bağlama duyarlı sağ tık menüleri ilişkisel ekranlarda ve diğer ortak modül
  tablolarında etkinleştirilmiştir.

## Sonraki zorunlu uyum işleri

- Bir sipariş satırını planlamada birden fazla üretim emrine bölmek.
- Reçete satırı pay/payda ve birim dönüşümlerini iş emri miktarlarına uygulamak.
- Kalıp–istasyon uygunluğunu planlama onayında zorunlu kılmak.
- Farklı çıkan boy için otomatik devam iş emri üretmek.
- Çoklu sevk adresi, şube ve ambar bazlı negatif stok politikasını tamamlamak.
- Paket etiketi, çeki listesi, sevk formu ve proforma şablon tasarım ekranını
  ürünleştirmek.
- Sağ tık komutlarını rol/yetki matrisinde tek tek açıp kapatmak.

Bu maddeler tamamlanmadan operasyon modülü “RIGEL ile tam eşdeğer” olarak
etiketlenmeyecektir. Maliyet modülü ise bu çalışmalardan bağımsız biçimde
mevcut net üretim bazlı hesaplarını sürdürür.
