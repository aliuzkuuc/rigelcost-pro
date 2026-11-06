from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGO_PATH = PROJECT_ROOT / "assets" / "logo.jpg"
PNG_PATH = PROJECT_ROOT / "assets" / "rigel_app_icon.png"
ICO_PATH = PROJECT_ROOT / "assets" / "rigel.ico"


def main() -> None:
    logo = Image.open(LOGO_PATH).convert("RGB")
    symbol_region = logo.crop((0, 0, logo.width, int(logo.height * 0.50)))
    difference = ImageChops.difference(
        symbol_region,
        Image.new("RGB", symbol_region.size, "white"),
    ).convert("L")
    mask = difference.point(lambda pixel: 255 if pixel > 12 else 0)
    bounds = mask.getbbox()
    if bounds is None:
        raise ValueError("Rigel işareti logo görselinde bulunamadı.")

    symbol = symbol_region.crop(bounds)
    target_height = 210
    target_width = round(symbol.width * target_height / symbol.height)
    symbol = symbol.resize((target_width, target_height), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (256, 256), (255, 255, 255, 255))
    left = (canvas.width - symbol.width) // 2
    top = (canvas.height - symbol.height) // 2
    canvas.paste(symbol, (left, top))
    canvas.save(PNG_PATH, format="PNG", optimize=True)
    canvas.save(
        ICO_PATH,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


if __name__ == "__main__":
    main()
