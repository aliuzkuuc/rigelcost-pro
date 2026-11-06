#!/bin/bash
# RigelCost portable zip — macOS/Linux
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(date +%Y%m%d-%H%M)"
RELEASE_DIR="$ROOT/release"
ZIP_NAME="RigelCost-Pro-${VERSION}-Portable.zip"
STAGE="$RELEASE_DIR/stage"

echo "==> Temizlik"
rm -rf "$STAGE"
mkdir -p "$STAGE" "$RELEASE_DIR"

if [[ ! -f "$ROOT/build/windows/build_windows.ps1" ]]; then
  echo "HATA: build/windows/build_windows.ps1 eksik; Windows EXE paketi uretilemez." >&2
  exit 1
fi

echo "==> Dosyalar kopyalanıyor"
rsync -a \
  --exclude '.git' \
  --exclude '.pytest_cache' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '*.zip' \
  --exclude 'release' \
  --exclude '_ref_satis' \
  --exclude '.DS_Store' \
  --exclude '.venv' \
  --exclude 'dist' \
  --exclude '.windows-build' \
  "$ROOT/" "$STAGE/RigelCost/"

if [[ ! -f "$STAGE/RigelCost/build/windows/build_windows.ps1" ]]; then
  echo "HATA: stage kopyasinda build/windows eksik kaldı." >&2
  exit 1
fi

echo "==> Testler çalıştırılıyor"
cd "$ROOT"
python3 -m pytest tests/ -q
QT_QPA_PLATFORM=offscreen python3 scripts/smoke_workflow.py
QT_QPA_PLATFORM=offscreen python3 scripts/ilk_kurulum_kontrol.py

echo "==> ZIP oluşturuluyor"
cd "$STAGE"
zip -rq "$RELEASE_DIR/$ZIP_NAME" RigelCost -x "*.pyc" -x "*__pycache__*"
rm -rf "$STAGE"

SIZE="$(du -h "$RELEASE_DIR/$ZIP_NAME" | awk '{print $1}')"
echo ""
echo "BUILD TAMAM"
echo "Paket : $RELEASE_DIR/$ZIP_NAME ($SIZE)"
echo ""
echo "Kurulum:"
echo "  1. ZIP'i aç"
echo "  2. macOS: RigelCost/BASLAT.command çift tıkla"
echo "     veya: cd RigelCost && pip3 install -r requirements.txt && python3 main.py"
echo "  3. Windows: RigelCost/build/windows/build_windows.ps1 ile EXE üret"
