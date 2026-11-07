"""Zamienia surowe rendery PNG na obrazy WebP i kopiuje modele GLB do public/.

Uzycie: python optimize.py
"""
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out"
PUB = HERE.parent.parent / "public" / "assets"
IMG_P = PUB / "img" / "p"
IMG_S = PUB / "img" / "s"
MODELS = PUB / "models"


def save(im, path, width, quality=80):
    r = im.copy()
    if r.width != width:
        r = r.resize((width, round(r.height * width / r.width)), Image.LANCZOS)
    r.save(path, "WEBP", quality=quality, method=6)


def product_image(src):
    slug = src.parent.name
    dest = IMG_P / slug
    dest.mkdir(parents=True, exist_ok=True)
    stem = src.stem  # np. 8mm-hero
    im = Image.open(src).convert("RGB")
    save(im, dest / f"{stem}-1200.webp", 1200, 82)
    save(im, dest / f"{stem}-600.webp", 600, 78)
    if stem.endswith("-macro"):
        # probka koloru do wyboru wariantu: srodek kadru, gdzie jest ostro
        w, h = im.size
        side = int(min(w, h) * 0.34)
        cx, cy = w // 2, int(h * 0.5)
        crop = im.crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)).resize((96, 96), Image.LANCZOS)
        crop.save(dest / f"{stem[:-6]}-swatch.webp", "WEBP", quality=82, method=6)
    return stem


def scene_image(src):
    IMG_S.mkdir(parents=True, exist_ok=True)
    im = Image.open(src).convert("RGB")
    w = im.width
    save(im, IMG_S / f"{src.stem}-{w}.webp", w, 84)
    save(im, IMG_S / f"{src.stem}-{round(w / 2)}.webp", round(w / 2), 80)
    return src.stem


def main():
    pngs = sorted((OUT / "produkty").glob("*/*.png"))
    with ThreadPoolExecutor(10) as ex:
        print(len(list(ex.map(product_image, pngs))), "zdjec produktow")
        print(len(list(ex.map(scene_image, sorted((OUT / "sceny").glob("*.png"))))), "scen")
    count = 0
    for glb in (OUT / "produkty").glob("*/*.glb"):
        d = MODELS / glb.parent.name
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(glb, d / glb.name)
        count += 1
    print(count, "modeli GLB")


if __name__ == "__main__":
    main()
