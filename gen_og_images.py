#!/usr/bin/env python3
"""Generate share/OG images (1200x630) for the two listicle pages.

Dark theme matching the site; shows the title + top-3 roles with score bars so a
shared link previews the actual ranking. Run: python3 gen_og_images.py
"""
import json, os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web", "en")
JOBS = json.load(open(os.path.join(WEB, "jobs.json")))
import importlib.util
spec = importlib.util.spec_from_file_location("gsp", os.path.join(ROOT, "gen_seo_pages.py"))
gsp = importlib.util.module_from_spec(spec); spec.loader.exec_module(gsp)
CURATED, band = gsp.CURATED, gsp.band

BG, SURF, BORDER = (9, 9, 11), (24, 24, 27), (39, 39, 46)
WHITE, GREY = (250, 250, 250), (161, 161, 170)

def font(sz, bold=True):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
              "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/HelveticaNeue.ttc",
              "/Library/Fonts/Arial.ttf"):
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
    return ImageFont.load_default()

def make(slug, mode, title, out):
    ranked = sorted(((k, JOBS[k]["name"], JOBS[k]["base"]) for k in CURATED if k in JOBS),
                    key=lambda x: -x[2] if mode == "risk" else x[2])[:3]
    img = Image.new("RGB", (1200, 630), BG)
    d = ImageDraw.Draw(img)
    d.text((70, 60), "WORKRADAR", font=font(30), fill=GREY)
    # title (wrap to 2 lines)
    words, lines, cur = title.split(), [], ""
    f_title = font(64)
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f_title) > 1060 and cur:
            lines.append(cur); cur = w
        else:
            cur = t
    lines.append(cur)
    y = 120
    for ln in lines[:2]:
        d.text((70, y), ln, font=f_title, fill=WHITE); y += 78
    # top-3 rows
    y = max(y + 30, 340)
    f_row, f_v = font(38), font(38)
    for i, (k, name, score) in enumerate(ranked, 1):
        _, _, _, hexc = band(score)
        rgb = tuple(int(hexc.lstrip("#")[j:j+2], 16) for j in (0, 2, 4))
        d.rounded_rectangle((70, y, 1130, y + 72), radius=16, fill=SURF, outline=BORDER, width=1)
        d.text((92, y + 16), f"{i}", font=f_row, fill=GREY)
        d.text((150, y + 16), name[:34], font=f_row, fill=WHITE)
        bx0, bx1 = 820, 1050
        d.rounded_rectangle((bx0, y + 30, bx1, y + 42), radius=6, fill=BORDER)
        d.rounded_rectangle((bx0, y + 30, bx0 + int((bx1 - bx0) * score / 100), y + 42), radius=6, fill=rgb)
        d.text((1070, y + 16), str(score), font=f_v, fill=rgb)
        y += 84
    d.text((70, 578), "workradar · task-level AI exposure · not a prediction", font=font(24, False), fill=(90, 90, 99))
    img.save(out, "PNG")
    print("wrote", os.path.basename(out))

def main():
    make("most-at-risk-jobs-from-ai", "risk", "Jobs Most at Risk From AI (2026)",
         os.path.join(WEB, "og-most-at-risk.png"))
    make("safest-jobs-from-ai", "safe", "Safest Jobs From AI (2026)",
         os.path.join(WEB, "og-safest.png"))

if __name__ == "__main__":
    main()
