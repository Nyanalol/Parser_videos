"""Genera el icono de la aplicación (assets/icon.ico).

Dibuja un cuadrado redondeado con degradado azul y un triángulo de "play"
blanco. Requiere Pillow (solo para generar el asset; no es dependencia de la app).

    python tools/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon.ico"

SIZE = 256


def _rounded_background(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Degradado vertical azul -> azul oscuro.
    top = (45, 125, 230)
    bottom = (20, 60, 140)
    for y in range(size):
        t = y / size
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Máscara con esquinas redondeadas.
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * 0.22), fill=255
    )
    img.putalpha(mask)
    return img


def _play_triangle(draw: ImageDraw.ImageDraw, size: int) -> None:
    w = size * 0.30
    h = size * 0.34
    cx, cy = size / 2 + size * 0.03, size / 2
    points = [
        (cx - w / 2, cy - h / 2),
        (cx - w / 2, cy + h / 2),
        (cx + w / 2, cy),
    ]
    draw.polygon(points, fill=(255, 255, 255, 240))


def main() -> None:
    base = _rounded_background(SIZE)
    _play_triangle(ImageDraw.Draw(base), SIZE)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    base.save(OUT, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Icono generado en {OUT}")


if __name__ == "__main__":
    main()
