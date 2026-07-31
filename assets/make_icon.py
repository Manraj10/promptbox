"""Render the Promptbox app icon.

The mark is a terminal caret and cursor bar inside a rounded square: a prompt,
in a box. Drawn at 4x and downsampled so the curves and strokes stay clean at
16px, where most of the detail has to survive.

    python assets/make_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent
SIZES = [16, 24, 32, 48, 64, 128, 256]
SS = 4  # supersample factor

BG = (20, 20, 24, 255)
EDGE = (58, 58, 68, 255)
CARET = (143, 211, 168, 255)   # sage, matches the UI accent
BAR = (242, 242, 244, 255)


def render(px: int) -> Image.Image:
    n = px * SS
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    pad = n * 0.055
    radius = n * 0.225
    d.rounded_rectangle([pad, pad, n - pad, n - pad], radius=radius,
                        fill=BG, outline=EDGE, width=max(1, int(n * 0.018)))

    stroke = max(1, int(n * 0.075))

    # caret  >
    x0, ymid = n * 0.30, n * 0.50
    reach, rise = n * 0.155, n * 0.145
    d.line([(x0, ymid - rise), (x0 + reach, ymid)], fill=CARET,
           width=stroke, joint="curve")
    d.line([(x0 + reach, ymid), (x0, ymid + rise)], fill=CARET,
           width=stroke, joint="curve")

    # cursor bar
    bx0, bx1 = n * 0.545, n * 0.715
    by = ymid + rise
    d.line([(bx0, by), (bx1, by)], fill=BAR, width=stroke)

    return img.resize((px, px), Image.LANCZOS)


def main() -> None:
    frames = [render(s) for s in SIZES]
    ico = OUT / "promptbox.ico"
    frames[-1].save(ico, format="ICO",
                    sizes=[(s, s) for s in SIZES])
    frames[-1].save(OUT / "icon-256.png")
    render(512).save(OUT / "icon-512.png")
    print(f"wrote {ico.name} ({', '.join(str(s) for s in SIZES)}), "
          f"icon-256.png, icon-512.png")


if __name__ == "__main__":
    main()
