# Rigel Cost Pro v4.0.0

Rigel Cost Pro, alüminyum ekstrüzyon üretiminde 15 ana fabrika giderini
hesaplayan ve ayrıntılı gider kayıtlarını yöneten masaüstü uygulamasıdır.

Arayüz ve geliştirme: **ALİ UZKUC**

## İşletme modülleri

Rigel'e özgü açılır sol menü aşağıdaki departmanlara ayrılmıştır:

- Maliyet
- Satış
- Satın Alma
- Malzeme Yönetimi
- Kalıphane
- Üretim
- Sevkiyat
- Bakım
- Raporlar
- Ayarlar

Maliyet Ana, gider alt sekmeleri, palet/paketleme ve mevcut stok ekranları
aynen çalışmaya devam eder. v4.0.0 yerel kontrol sürümünde müşteri, profil,
kalıp, satış siparişi, üretim, iş emirleri, paket ve sevkiyat çekirdek ekranları
aynı ilişkisel yerel veritabanına bağlanmıştır. Satın alma ve bakımın ayrıntılı
canlı akışları sonraki kontrol aşamasındadır.

Bağlantılı canlı iş akışı kayıtları `rigel_workflow.db` içinde; mevcut maliyet
ve gider kayıtlarından ayrı tutulur. Profilin üretim özelliklerine uyan reçete
ve rota seçilir. Satış siparişi onaylandığında üretim emri ve sıralı iş emirleri
oluşur; bir istasyon bitmeden sonraki istasyona giriş engellenir. Son işlem
mamul stok oluşturur; paketleme sevke hazır stoka, sevkiyat ise teslim edilen
miktara bağlı çalışır.

Pres fişlerinde brüt/net fire, fire yüzdesi, kg/saat, teorik net kg, gramaj
farkı ve tenefer kullanımı otomatik hesaplanır. Kalıp kartlarında kalan ömür
ve kullanım yüzdesi; bakım emirlerinde duruş süresi ve plan uyumu hesaplanır.

Program açıldığında önce **Yönetim Paneli (HOME)** görünür. Maliyet hesabı
yalnızca kullanıcı **Maliyet Ana** bölümünü açtığında ekrana gelir.
HOME ekranında hızlı işlemler, aktif/hazırlanan modüller, piyasa özeti ve
yerel veri durumu bulunur; hiçbir maliyet sonucu gösterilmez. Sağ üstteki
**Çıkış** düğmesi programı kapatmadan önce kullanıcı onayı ister.
Sayısal alanlar veya açılır seçimler odaktayken fare tekerleği değerleri
değiştirmez; tekerlek yalnızca sayfayı kaydırmak için kullanılır.

İlk açılışta bütün yetkilere sahip **Patron** hesabı oluşturulur. Sonraki
açılışlarda kullanıcı adı ve şifre istenir. Patron, Ayarlar içindeki
**Kullanıcı ve Yetkiler** ekranından Satış, Satın Alma, Malzeme, Kalıphane,
Üretim, Sevkiyat, Bakım ve Maliyet rollerini tanımlar. Kullanıcı yalnızca
izin verilen bölümleri görür. Parolalar PBKDF2-SHA256 ile tuzlanmış özet
olarak saklanır; düz metin parola kaydedilmez.

**İlk Kurulum Veri Aktarımı** patronun ilk girişinde yalnız bir kez açılır.
Excel dışa aktarımlarını veya fabrika ağındaki `rigel.config` üzerinden yetkili
SQL Server tablolarını salt okunur alır. Şifreli bağlantıda bilgiler bir kez
istenir ve parola kaydedilmez. Kaynak sisteme yazma/silme yapmaz; aynı aktarım
tekrarlandığında kopya kayıt oluşmaz. `SharedFiles`, `SharedFiles10` ve
`SharedFiles52` içindeki PDF/resimler klasör kayıt kimliğiyle doğru profil ve
kalıp kartına bağlanır. Sonraki açılışlarda normal kullanıcılar aktarım menüsünü
görmez; yalnız `aliuzkuc` geliştirici hesabı yeniden açabilir.

Excel ile ilk aktarımda `Profil Listesi`, `Kalıp Listesi` ve `Üretilecek
Kalıplar Listesi` dosyalarıyla `SharedFiles` klasörü aynı ana klasör altında
çıkarılmalıdır. Kullanıcı bu ana klasörü bir kez seçer; program alt klasörleri
kendisi tarar ve aynı aktarım tekrar çalıştırıldığında mükerrer kart oluşturmaz.

## Kurulum

### Windows 10/11 — Python gerektirmeyen EXE

Windows bilgisayarda bu kaynak klasörünü ZIP'ten çıkarıp
`WINDOWS-EXE-OLUSTUR.bat` dosyasına çift tıklayın. Otomatik derleme sonunda
`release` klasöründe iki dağıtım seçeneği oluşur:

- `RigelCost-Pro-v4.0.0-Setup.exe`: Kurulum ve kısayol oluşturan paket.
- `RigelCost-Pro-v4.0.0-Portable.zip`: Kurulum gerektirmeyen gösterim paketi.

Bu iki çıktı başka Windows 10/11 64-bit bilgisayarlarda Python kurulmadan
çalışır. Ayrıntılar `WINDOWS-KURULUM-REHBERI.md` dosyasındadır.

### macOS — kaynak koddan çalıştırma

Proje klasöründe:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

Sonraki açılışlarda Finder'dan `BASLAT.command` dosyasına çift tıklayın; varsa
proje içindeki `.venv` ortamını kullanır. Bu kaynak paketi macOS için bağımsız
`.app` oluşturmaz; ilk kurulumda Python ve internet bağlantısı gerekir.
SQL Server aktarımı Windows'a özeldir; macOS'ta yerel SQLite ve Excel aktarımı
kullanılabilir.

### Windows'ta kaynak koddan çalıştırma

Windows kaynak kodu kurulumu için `python -m pip install -r requirements.txt`
komutunu kullanın. SQL Server aktarımı için `pyodbc` yalnız Windows'ta kurulur.
Python gerektirmeyen EXE/kurulum paketi üretmek için yukarıdaki Windows
yönergelerini izleyin.

Program kullanıcı/şifre ve lisans ekranı göstermeden doğrudan HOME
sayfasında açılır. Lisanslama sonraki geliştirme aşamasına ertelenmiştir.

## Üretime göre hesap

- Billet, fire, elektrik, doğalgaz ve su doğrudan net üretime göre hesaplanır.
- Gider referans üretimi kullanılmaz.
- Maaş doğrudan Maliyet Ana'da aylık toplam hakediş olarak girilir.
- Kira, yemek, araç yakıt, genel gider, nakliye, tenefer, kalıp, fabrika iş
  akışı, amortisman ve paketleme satırları Gider Alt Sekmeleri'nden girilir.
- Alt sekmelerde oluşan aylık toplamlar Maliyet Ana'daki salt okunur alanlara
  otomatik aktarılır ve üretime göre ikinci kez ölçeklenmez.
- Maliyet Ana; elektrik, doğalgaz, su, maaş, kira, yemek, araç yakıt, genel
  gider, nakliye, tenefer, kalıp, fabrika iş akışı, amortisman, fire-fason ve
  paketleme olmak üzere 15 kalemi ayrı ayrı gösterir.
- Bu 15 kalem TL'den USD'ye çevrilir; toplam USD, net üretim kg'sına bölünerek
  **USD/kg** ve **USD/ton** fabrika maliyeti hesaplanır.
- Hammadde tutarı ve “toplam profil maliyeti” Maliyet Ana sonucuna eklenmez.
  LME + prim yalnızca Fire-Fason sekmesindeki nihai metal kaybını değerlemek
  için kullanılır.

## Gider alt sekmeleri

- Bina Kirası
- Yemek: gündüz/gece yemek sayısı × gün sayısı × farklı birim fiyatlar
- Araç Yakıt: güzergâh, km/gün, gün, toplam km, yakıt tipi, L/100 km ve fiyat
- Genel Gider: girilmiş Tutar; Tutar boşsa adet/kişi × birim fiyat
- Nakliye: adet × birim fiyat
- Tenefer: kg × birim fiyat
- Kalıp Maliyeti: adet × birim fiyat
- Fabrika İş Akışı ve Amortisman: satır tutarları toplamı
- Fire-Fason: brüt/net, fire, geri dönüşüm, nihai kayıp ve fason hesabı
- Palet Hesabı: net üretimden otomatik palet, kereste hacmi, karton
  köşebent, şerit çember, sarma naylon ve streç film hesabı
- Paketleme: Palet Hesabı'ndan otomatik gelen beş kalem ile kullanıcı
  tarafından girilebilen ilave KG/M3/ADET/METRE giderleri
- Bütün gider kayıtlarında açıklama için Not alanı

Palet sayısı `yukarı yuvarla(net üretim / ortalama palet kg)` formülüyle
hesaplanır. Yanlı/yansız oranları, kereste ölçüleri ve fiyatı, palet başı
köşebent/çember, naylon sarım oranı ve USD/ton fiyatı değiştirilebilir.
Streç film adedi 200.000 kg'daki 168 adet temelinden net üretime oranlanır
ve yukarı yuvarlanır. Beş kalemin toplamı Paketleme ve Maliyet Ana
ekranlarına otomatik aktarılır.

Alt sekme kayıtları yerel kullanıcı veri klasöründe otomatik saklanır.
Dar pencerede Maliyet Ana formu tek sütuna geçerek sağdan taşmayı önler.

## Excel uyumlu temel katsayılar

- Brüt billet: `net üretim / 0,85`
- İlk fire: `brüt billet - net üretim`
- Geri kazanılan fire: `ilk fire × 0,97`
- Nihai metal kaybı: `ilk fire × 0,03`
- Nihai metal kaybı değeri: `nihai kayıp × (LME + prim) × USD/TL`
- Fason ergitme: `geri kazanılan fire × 0,25 USD/kg`
- Elektrik: `567 kWh/ton`
- Doğalgaz: `48 Sm³/ton`
- Su: `0,5 m³/ton`

## Piyasa verileri

Üst bilgi bandındaki **Kurları / LME'yi Güncelle** düğmesi:

- USD/TL ve EUR/TL efektif satış kurlarını TCMB'den,
- LME alüminyum fiyatını doğrudan Westmetall tablosunun en üst tarihli
  **LME Aluminium Cash-Settlement** sütunundan

alır. Son başarılı değerler önbelleğe kaydedilir. Bağlantı kurulamazsa
uygulama mevcut veya elle girilen değerleri korur.

## Raporlar

PDF ve Excel çıktılarında iç kullanıma ait “15 kalem” ve “alt sekme
toplamı” ifadeleri gösterilmez. Toplam satırı **Fabrika Maliyeti Toplamı**
olarak yazılır ve raporlarda geliştirici adı **ALİ UZKUC** görünür.

## Stok takibi

Stok modülü aşağıdaki grupları destekler:

- Billet
- Profil / mamul
- Hurda / fire
- Ambalaj
- Sarf malzemesi
- Yedek parça
- Diğer

Her stok kartında kod, ad, kategori, birim, minimum stok, mevcut miktar,
ağırlıklı ortalama maliyet ve stok değeri tutulur. Giriş, çıkış ve sayım
hareketleri tarih, belge numarası ve açıklamayla kaydedilir. Mevcut miktardan
fazla çıkış engellenir; minimum seviyeye inen kartlar kırmızı gösterilir.
Veriler uygulamanın yerel SQLite veritabanında kalıcı olarak saklanır.

## Raporlar

Hesap tamamlandıktan sonra biçimlendirilmiş Excel ve PDF raporu
oluşturulabilir. Raporlarda 15 fabrika gideri, fire zinciri, tüketimler,
toplam USD, USD/kg ve USD/ton yer alır; hammadde/toplam profil maliyeti
gösterilmez.

## Test

```bash
python3 -m unittest discover -s tests -v
```

Testler 15 kalem fabrika maliyetini, 150/200/300 ton enerji ve fire
hesaplarını, gider alt sekmelerini, ekranın dar/geniş yerleşimini,
raporları, piyasa verisi ayrıştırmasını ve yeni işletme modüllerinin
formül/iş akışı bağlantılarını kontrol eder.
