#!/usr/bin/env python3
"""Generate PWA / app icons for WorkRadar (radar rings + WR monogram, dark).
Outputs to web/en/: icon-192.png, icon-512.png, icon-maskable-512.png, apple-touch-icon.png
"""
import os
from PIL import Image, ImageDraw, ImageFont

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "en")
BG = (9, 9, 11)
AMBER = (245, 158, 11)
ROSE = (225, 29, 72)
WHITE = (250, 250, 250)


def font(sz):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/System/Library/Fonts/HelveticaNeue.ttc"):
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
    return ImageFont.load_default()


def make(size, out, pad_ratio=0.0, bg=BG):
    img = Image.new("RGB", (size, size), bg)
    d = ImageDraw.Draw(img)
    c = size / 2
    inner = size * (1 - 2 * pad_ratio)          # maskable safe area
    base = inner / 2
    rings = [(base * 0.92, AMBER, 2), (base * 0.66, AMBER, 2), (base * 0.40, ROSE, 2)]
    for r, col, w in rings:
        lw = max(3, int(size * 0.016))
        d.ellipse((c - r, c - r, c + r, c + r), outline=col, width=lw)
    f = font(int(inner * 0.34))
    d.text((c, c - inner * 0.02), "WR", font=f, anchor="mm", fill=WHITE)
    img.save(out)
    print(os.path.basename(out))


if __name__ == "__main__":
    make(192, os.path.join(WEB, "icon-192.png"))
    make(512, os.path.join(WEB, "icon-512.png"))
    make(512, os.path.join(WEB, "icon-maskable-512.png"), pad_ratio=0.14)  # maskable safe padding
    make(180, os.path.join(WEB, "apple-touch-icon.png"))
