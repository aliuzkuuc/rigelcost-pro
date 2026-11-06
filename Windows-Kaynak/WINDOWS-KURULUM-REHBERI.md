# Rigel Cost Pro v4.0.0 — Windows EXE hazırlama

Bu paket Windows 10/11 64-bit bilgisayarda çalıştırılabilir bir uygulama ve
kurulum dosyası üretir.

## Tek seferlik EXE üretimi

1. ZIP dosyasını Windows bilgisayarda **OneDrive / iCloud dışında** bir
   klasöre tamamen çıkarın (örnek: `C:\Projects\RigelCost`).
2. Çıkan klasörde `build\windows\build_windows.ps1` dosyasının olduğunu
   kontrol edin. Yoksa paket eksiktir; güncel TEST ZIP'ini yeniden alın.
3. İnternet bağlantısının açık olduğundan emin olun.
4. `WINDOWS-EXE-OLUSTUR.bat` dosyasına çift tıklayın.
5. Windows kurulum izni isterse onaylayın.
6. İşlem gerçekten başarılı olursa `release` klasörü otomatik açılır.
   Betik veya `release` çıktısı yoksa ekranda **ISLEM BASARISIZ** yazar;
   `release` açılmaz.

İlk derlemede gerekli Python ve Inno Setup araçları bilgisayarda yoksa
Windows Paket Yöneticisi aracılığıyla otomatik kurulur. Bu araçlar yalnızca
EXE üretmek içindir. Oluşturulan uygulamanın çalışacağı bilgisayarlarda
Python veya başka bir geliştirme aracı gerekmez.

Derleyici özellikle Python 3.12 kullanır. Bilgisayarda Python 3.14 gibi
başka bir sürüm bulunsa bile onu kullanmaz. Her çalıştırmada önceki yarım
derleme ortamı temizlenir ve sıfırdan hazırlanır.

Windows veya antivirüs bir derleme dosyasını kısa süreli kullanıyorsa paket
oluşturucu dosyaları güvenli bir hazırlık klasörüne tekrar deneyerek kopyalar
ve taşınabilir ZIP işlemini otomatik olarak yeniden dener.
Gerekli araçların kurulumunda bozuk Microsoft Store kaynağı kullanılmaz;
paketler doğrudan Windows Package Manager `winget` kaynağından alınır.
Python paketleri ve PyInstaller çıktısı, Windows uzun yol sınırına
takılmaması için otomatik olarak kısa `%TEMP%\RCB` dizininde hazırlanır.

## Oluşan dosyalar

- `RigelCost-Pro-v4.0.0-Setup.exe`: Normal Windows kurulumu, Başlat menüsü,
  **Uygulamalar ve özellikler** kaldırma girişi ve isteğe bağlı masaüstü
  kısayolu.
- `RigelCost-Pro-v4.0.0-Portable.zip`: Kurulum yapmadan gösterim için
  taşınabilir klasör. ZIP'i çıkarıp `RIGEL-COST-PRO-BASLAT.bat` veya
  `RigelCostPro.exe` çalıştırılır. Kaldırmak için aynı klasördeki
  `KALDIR.bat` kullanılır.

## Hızlı test (kurulum olmadan)

1. `release\RigelCost-Pro-v4.0.0-Portable.zip` dosyasını **OneDrive dışında**
   bir klasöre çıkarın. Örnek: `C:\RigelTest`
2. Çıkan klasörde `RIGEL-COST-PRO-BASLAT.bat` dosyasına çift tıklayın.

Bu yöntem `Setup.exe` bozuksa bile programı hemen test etmenizi sağlar.

## "The setup files are corrupted" hatası

Bu hata genellikle kurulum dosyasının yarım kalması veya OneDrive/antivirüs
tarafından bozulmasından kaynaklanır. Şu sırayı deneyin:

1. **Portable ZIP ile test edin** (yukarıdaki hızlı test adımları).
2. Proje klasörünü OneDrive / iCloud / ağ sürücüsü dışına taşıyın.
   Örnek: `C:\Projects\RigelCost`
3. Eski `release` klasörünü silin.
4. `WINDOWS-EXE-OLUSTUR.bat` dosyasını yeniden çalıştırın.
5. Derleme bittikten sonra `Setup.exe` boyutunun en az ~40 MB olduğunu
   kontrol edin. Çok küçükse derleme yarım kalmış demektir.
6. Windows Defender veya antivirüs geçici olarak kapatılamıyorsa,
   `release` klasörünü istisna listesine ekleyin.

Kurulum dosyası yine bozuksa portable ZIP ile dağıtım yapılabilir; program
aynıdır.

## İlk açılış

İlk açılışta bütün yetkilere sahip patron hesabı oluşturulur. Sonraki
açılışlarda kullanıcı adı ve şifre ile giriş yapılır. Lisans ekranı yoktur.
Kullanıcı yalnızca patronun izin verdiği bölümleri görür.

İlk patron girişinde **İlk Kurulum Veri Aktarımı** yalnız bir kez otomatik
açılır. Fabrika ağına bağlı bilgisayarda `rigel.config` seçilerek SQL
Server'dan salt okunur tam aktarım başlatılabilir. Kaynak bağlantısı şifreliyse
sunucu, veritabanı ve salt-okuma kullanıcısı yalnız bu işlem için bir kez
istenir; parola Rigel'e kaydedilmez. Bu işlem kaynak sistemi değiştirmez.
`SharedFiles`, `SharedFiles10` ve `SharedFiles52` altındaki PDF, görsel ve
teknik çizimler Rigel veri klasörüne kopyalanıp profil/kalıp kartlarına bağlanır.
Aktarım ekranı daha sonra normal kullanıcılara görünmez; yalnız `aliuzkuc`
geliştirici hesabı **Ayarlar → İlk Veri Aktarımı** yoluyla yeniden açabilir.
SQL aktarımı yapılan Windows bilgisayarda Microsoft ODBC Driver, SQL Server
Native Client veya klasik SQL Server sürücülerinden biri bulunmalıdır.

SQL bağlantısı kullanmadan profil ve kalıpları toplu yüklemek için RAR
dosyalarını önce ayrı bir klasöre çıkarın. Önerilen yapı şöyledir:

```text
RIGEL-ILK-AKTARIM
├── exceller
│   ├── Profil Listesi (profil kartları ).xlsx
│   ├── Kalıp Listesi (kalıp kartları ).xlsx
│   └── Üretilecek Kalıplar Listesi ( imalattaki kalıplar).xlsx
└── SharedFiles
    ├── PROFIL
    ├── KALIP
    ├── SIPARIS
    ├── PRESURETIM
    └── STOK
```

Aktarım ekranında **EXCEL KLASÖRÜ SEÇ VE AKTAR** düğmesiyle en üstteki
`RIGEL-ILK-AKTARIM` klasörünü seçin. Program alt klasörlerdeki Excel'leri ve
`SharedFiles` belgelerini birlikte tarar. Profil/kalıp kartları, gramajlar,
firma kodları ve durumlar toplu oluşturulur; PDF/JPG dosyaları ilgili karta
bağlanır. RAR dosyasını veya eski program klasörünü doğrudan seçmeyin.

Canlı USD/TL, EUR/TL ve LME değerleri için internet bağlantısı gerekir.
İnternet yoksa program son kaydedilen piyasa değerlerini kullanır.

## Verilerin saklandığı yer

Piyasa önbelleği, gider ayrıntıları, işletme kartları, ekler ve stok
veritabanı Windows kullanıcı veri klasöründe saklanır. Programı güncellemek
veya yeniden kurmak bu verileri silmez.

Tipik konumlar (Qt `AppDataLocation` / `AppConfigLocation`):

- `%LOCALAPPDATA%\Rigel Alüminyum\Rigel Cost Pro` — SQLite DB, ekler, önbellek
- `%APPDATA%\Rigel Alüminyum\Rigel Cost Pro` — yapılandırma (`database.json` vb.)
- `%USERPROFILE%\.rigelcost` — yedek / fabrika ayarı (`rigel.config`)
- `%USERPROFILE%\Documents\RigelCost_*` — dışa aktarılan raporlar

## Programı kaldırma

### Kurulum (Setup.exe) ile yüklendiyse

1. Programı kapatın.
2. **Başlat → Rigel Cost Pro Kaldır** veya
   **Ayarlar → Uygulamalar → Rigel Cost Pro → Kaldır** seçin.
3. Kaldırma sihirbazında türü seçin:
   - **Normal kaldır** — yalnız program klasörü
     (`%LOCALAPPDATA%\Programs\Rigel Cost Pro`). Kullanıcı verileri kalır.
   - **Temiz kaldır / Tüm dosyaları kaldır** — program + yukarıdaki tüm
     veri klasörleri, ekler, ayarlar, `RigelCost_*` belgeler ve ilgili
     kayıt defteri anahtarları. İkinci bir onay ister; geri alınamaz.

### Portable ZIP ile kullanıldıysa

1. Programı kapatın.
2. Çıkarılan klasördeki `KALDIR.bat` dosyasına çift tıklayın.
3. `[1] Normal kaldir` veya `[2] Temiz kaldir / Tum dosyalari kaldir`
   seçin; onayları `E` ile verin.

Portable klasörde `KALDIR.bat` yoksa klasörü elle silebilirsiniz; temiz
kaldırma için yukarıdaki veri yollarını da elle silmeniz gerekir.

## Windows uyarısı

İlk gösterim sürümü dijital kod imzası taşımadığı için Windows SmartScreen
"Bilinmeyen yayıncı" uyarısı gösterebilir. Bu durumda "Daha fazla bilgi"
ve ardından "Yine de çalıştır" seçilebilir. Ticari dağıtımdan önce kod
imzalama sertifikası eklenmesi önerilir.

## Derleme hata verirse

`build\windows\build_windows.ps1 bulunamadi` benzeri bir mesaj görürseniz
ZIP eksik çıkarılmıştır veya eski bir pakettir. Güncel
`RigelCost-Pro-TEST-*.zip` dosyasını yeniden indirip klasörü silerek
baştan çıkarın; `build\windows` altında en az şu dosyalar olmalıdır:
`build_windows.ps1`, `RigelCostPro.spec`, `installer.iss`,
`RIGEL-COST-PRO-BASLAT.bat`, `KALDIR.bat`, `requirements-build.txt`,
`version_info.txt`.

Eski pakette oluşmuş `.windows-build`, `dist` veya `release` klasörlerini
elle silmeniz gerekmez. Güncel `WINDOWS-EXE-OLUSTUR.bat` dosyası geçici
derleme klasörlerini güvenli şekilde temizler. Hata devam ederse terminalin
en altındaki son 20 satırın ekran görüntüsünü paylaşın.
