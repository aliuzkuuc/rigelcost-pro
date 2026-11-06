# Rigel Cost Pro v4.0.0 — macOS'ta çalıştırma

Bu kaynak paketi macOS'ta Python üzerinden çalışır. Bağımsız bir `.app`
dosyası içermez.

## İlk kurulum

1. ZIP'i Finder'da tamamen çıkarın.
2. Mac'te Python 3.14 kurulu olmalıdır. Terminal'i açın ve proje klasörüne geçin.
   Örneğin klasör İndirilenler içindeyse:

   ```bash
   cd ~/Downloads/RigelCost
   ```

3. Projeye özel Python ortamını ve gerekli paketleri kurun:

   ```bash
   python3.14 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

4. Programı açın:

   ```bash
   python main.py
   ```

## Sonraki açılışlar

Finder'da `BASLAT.command` dosyasına çift tıklayın. Dosya proje içindeki
`.venv` ortamını otomatik kullanır. macOS güvenlik uyarısı gösterirse dosyaya
sağ tıklayıp **Aç** seçeneğini kullanın. İzin hatası alırsanız Terminal'de
proje klasöründen bir kez `chmod +x BASLAT.command` çalıştırın.

Bu kaynak sürümünde yerel SQLite veritabanı ve Excel aktarımı kullanılabilir.
Eski fabrika sisteminden tam SQL Server aktarım ekranı Windows'a özeldir.
Mac'te ayrıca merkezi SQL Server bağlantısı kullanacaksanız önce Terminal'de
ODBC yöneticisini ve Python bileşenini kurun, ardından SQL Server için uygun
ODBC sürücüsünü yükleyin:

```bash
brew install unixodbc
source .venv/bin/activate
python -m pip install pyodbc
```

`pyodbc` bu temel Mac kurulumunda isteğe bağlıdır; proje bağımlılıklarında
Windows için otomatik kurulur. [pyodbc kurulum notları](https://github.com/mkleehammer/pyodbc#install)
ayrıntıları verir.

## Windows'ta çalıştırma

Windows 10/11 64-bit bilgisayarda ZIP'i çıkarıp `WINDOWS-EXE-OLUSTUR.bat`
dosyasına çift tıklayın. Oluşturulan `release` klasöründe kurulum dosyası ve
taşınabilir ZIP bulunur. Ayrıntılar için `WINDOWS-KURULUM-REHBERI.md` dosyasına
bakın.
