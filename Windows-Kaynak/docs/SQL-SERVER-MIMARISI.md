# Rigel Cost Pro — Merkezi SQL Server Mimarisi

## Hedef kurulum

- Her fabrikada bir Windows Server veya sürekli açık sunucu bilgisayar bulunur.
- SQL Server Express/Standard üzerinde yalnız Rigel'e ait `RIGEL_COST_PRO`
  veritabanı oluşturulur.
- Satış, üretim, kalıphane, sevkiyat ve yönetim bilgisayarlarındaki Rigel EXE
  istemcileri aynı veritabanına bağlanır.
- RIGEL veritabanına yazılmaz. İzin verilen eski kayıtlar yalnız ilk geçişte
  Rigel veritabanına alınır.
- Teknik çizim, PDF ve JPG dosyaları sunucudaki ortak Rigel klasöründe tutulur;
  dosya özeti ve bağlantısı SQL'deki `attachments` tablosunda yer alır.

## Ana iş akışı

1. Müşteri, profil, kalıp ve stok kartları oluşturulur.
2. Satış siparişi başlığına bir veya daha fazla sipariş satırı eklenir.
3. Üretim onayı verilen her satır için üretim emri açılır.
4. Profil reçetesindeki rota adımları iş emirlerine dönüşür.
5. Pres/termik/yüzey/paketleme kayıtları iş emrindeki üretilen ve bekleyen
   miktarları günceller.
6. Her giriş, çıkış ve transfer `stock_movements` tablosuna değişmez hareket
   satırı olarak yazılır.
7. Paketlenen ürünler hazır kasaya, ardından çeki listesi ve sevkiyata bağlanır.
8. Sipariş satırındaki sipariş, üretim, saha ve sevk miktarları tek kaynaktan
   hesaplanır.

## Güvenlik ve ticari kullanım

- Kullanıcı, rol ve işlem yetkileri sunucuda merkezi tutulur.
- SQL parolası düz metin kaydedilmez; Windows istemcide DPAPI ile korunur.
- Günlük kullanıcı SQL şema değiştirme yetkisine sahip olmaz.
- Ekleme, düzenleme, silme ve durum değişiklikleri `audit_log` tablosuna yazılır.
- Kritik tablolarda `rowversion` kullanılarak eşzamanlı düzenleme çakışmaları
  yakalanır.
- SQL Server yedeği ve ortak belge klasörü yedeği birlikte alınır.

## Sürüm yükseltme

`database/sqlserver` içindeki numaralı migration dosyaları sırayla ve transaction
içinde uygulanır. Uygulanan sürümler `schema_versions` tablosunda tutulur.
Başarısız migration geri alınır ve istemci eski şemayla yazmaya devam etmez.
