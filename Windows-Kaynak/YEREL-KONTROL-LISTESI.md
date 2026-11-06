# Rigel Cost Pro v4.0.0 — Yerel Windows Kontrolü

Bu sürümde amaç, merkez SQL Server kurmadan önce tek Windows bilgisayarda
bağlantılı işletme akışını ve mevcut maliyet modülünü doğrulamaktır. Ana veri
yerel ilişkisel SQLite veritabanında tutulur. Merkez SQL Server bu kontrolden
sonra devreye alınacaktır.

## Kurulum

1. Çalışan Rigel Cost Pro'yu kapatın.
2. Mümkünse `%LOCALAPPDATA%\Rigel Alüminyum\Rigel Cost Pro` klasörünün bir
   yedeğini alın.
3. `WINDOWS-EXE-OLUSTUR.bat` dosyasını çalıştırın.
4. `release\RigelCost-Pro-v4.0.0-Setup.exe` dosyasını çalıştırın.
5. Önceki sürüm kuruluysa aynı hedef klasöre kurabilirsiniz. Kullanıcı veri
   klasöründeki maliyet, gider, stok ve kullanıcı kayıtları silinmez.

## 1. Maliyet regresyon kontrolü

- Maliyet Ana açıldığında son kayıtlı değerlerin durduğunu kontrol edin.
- Net üretimi değiştirip elektrik, doğalgaz, su ve fire-fason sonuçlarını
  kontrol edin.
- Gider Alt Sekmeleri ve Palet Hesabı toplamlarının Maliyet Ana'ya geldiğini
  kontrol edin.
- PDF ve Excel raporu oluşturun.

## 2. Ana kartlar

- Satış / Müşteriler ekranında bir müşteri oluşturun.
- Kalıphane / Profil Kartları ekranında profil ve üretim özelliklerini girin.
- Profile uygun işlem sırasını rota olarak ekleyin. Örnek:
  `PRES → TERMİK GİRİŞ → TERMİK ÇIKIŞ → ÖN SEVK → SEVK HAZIR`.
- Profil veya kalıp kartına bir PDF/JPG ekleyip tekrar açın.

## 3. Satıştan üretime bağlı akış

- Satış Siparişleri ekranından en az iki satırlı sipariş oluşturun.
- Siparişi onaylayın; üretim emri ve rota adımları kadar iş emri oluştuğunu
  kontrol edin.
- İlk işlem bitmeden sonraki işlemi tamamlamayı deneyin. Programın bunu
  engellemesi gerekir.
- İşlemleri sırayla tamamlayın. Son işlem tamamlanınca üretilen miktar mamul
  stokta görünmelidir.

## 4. Paketleme ve sevkiyat

- Üretilenden fazla miktarı paketlemeyi deneyin. Program engellemelidir.
- Geçerli miktarı paketleyin; paket sevke hazır olarak görünmelidir.
- Paketi sevk edin; sevk edilen miktar sipariş satırına bağlanmalı ve sevke
  hazır stoktan düşmelidir.

## 5. Bir defalık eski veri aktarımı

- Eski sistem aktarımı yalnız kaynak okuma yetkisiyle kullanılmalıdır.
- Müşteri, profil, kalıp, reçete/rota ve bağlı dosyaların geldiğini kontrol
  edin.
- Kaynak sisteme hiçbir kayıt yazılmaz veya silinmez.
- Eski üretim hareketlerinin tüm tarihsel ayrıntısı v4.0.0 için tamamlandı
  kabul edilmemelidir; ayrı aktarım ve mutabakat kontrolünden geçecektir.

## Sonuç kaydı

Bir problem olursa şu üç bilgiyi birlikte kaydedin:

- Açık ekran ve yapılan işlem
- Girilen örnek değerler
- Hata mesajının veya yanlış sonucun ekran görüntüsü

