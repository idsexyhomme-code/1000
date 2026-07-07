#!/usr/bin/env python3
"""Generate Product Hunt launch gallery images (1270x760) + thumbnail (240x240).

Dark theme matching the site. Run: python3 gen_ph_images.py  → web/en/ph/*.png
"""
import json, os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web", "en")
OUT = os.path.join(WEB, "ph"); os.makedirs(OUT, exist_ok=True)
JOBS = json.load(open(os.path.join(WEB, "jobs.json")))
import importlib.util
spec = importlib.util.spec_from_file_location("gsp", os.path.join(ROOT, "gen_seo_pages.py"))
gsp = importlib.util.module_from_spec(spec); spec.loader.exec_module(gsp)
CURATED, band = gsp.CURATED, gsp.band

W, H = 1270, 760
BG, SURF, BORDER = (9, 9, 11), (24, 24, 27), (39, 39, 46)
WHITE, GREY, DIM = (250, 250, 250), (161, 161, 170), (120, 120, 130)
AMBER = (245, 158, 11)

def F(sz, bold=True):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
              "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/HelveticaNeue.ttc"):
        if os.path.exists(p):
            try: return ImageFont.truetype(p, sz)
            except Exception: pass
    return ImageFont.load_default()

def base():
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    d.text((64, 54), "WORKRADAR", font=F(30), fill=GREY)
    return img, d

def wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) > maxw and cur: lines.append(cur); cur = w
        else: cur = t
    lines.append(cur); return lines

def hero():
    img, d = base()
    for i, ln in enumerate(wrap(d, "What's your AI Risk Type?", F(78), 1140)):
        d.text((64, 180 + i * 92), ln, font=F(78), fill=WHITE)
    for i, ln in enumerate(wrap(d, "A 1-minute test: see which of your tasks AI is coming for — with sources, not hype.", F(34, False), 1120)):
        d.text((64, 380 + i * 46), ln, font=F(34, False), fill=GREY)
    d.rounded_rectangle((64, 520, 300, 588), radius=34, fill=WHITE)
    d.text((104, 538), "Free test", font=F(30), fill=(0, 0, 0))
    d.text((330, 538), "100+ roles · task-level · honest method", font=F(26, False), fill=DIM)
    img.save(os.path.join(OUT, "ph-01-hero.png")); print("ph-01-hero.png")

def ranking():
    img, d = base()
    d.text((64, 150), "Jobs most at risk from AI (2026)", font=F(52), fill=WHITE)
    ranked = sorted(((JOBS[k]["base"], JOBS[k]["name"], k) for k in CURATED),
                    key=lambda x: -x[0])[:6]
    y = 250
    for i, (score, name, k) in enumerate(ranked, 1):
        _, _, _, hexc = band(score); rgb = tuple(int(hexc.lstrip("#")[j:j+2], 16) for j in (0, 2, 4))
        d.rounded_rectangle((64, y, 1206, y + 68), radius=14, fill=SURF, outline=BORDER, width=1)
        d.text((90, y + 18), str(i), font=F(30), fill=GREY)
        d.text((150, y + 16), name, font=F(32), fill=WHITE)
        d.rounded_rectangle((900, y + 30, 1130, y + 40), radius=5, fill=BORDER)
        d.rounded_rectangle((900, y + 30, 900 + int(230 * score / 100), y + 40), radius=5, fill=rgb)
        d.text((1150, y + 16), str(score), font=F(30), fill=rgb)
        y += 80
    d.text((64, y + 6), "Ranked by task-level AI exposure. Directional, not a prediction.", font=F(24, False), fill=DIM)
    img.save(os.path.join(OUT, "ph-02-ranking.png")); print("ph-02-ranking.png")

def method():
    img, d = base()
    d.text((64, 150), "Honest by design", font=F(56), fill=WHITE)
    points = [
        ((59, 130, 246), "Task-level, not clickbait", "Every score breaks a job into tasks — see exactly what's exposed."),
        ((139, 92, 246), "Sources shown", "Anchored to public AI-exposure research where possible."),
        ((225, 29, 72), "A reference, not a prediction", "Scores are hand-estimated and labeled as such. No fear-bait."),
    ]
    y = 260
    for col, h, sub in points:
        d.rounded_rectangle((64, y, 1206, y + 118), radius=16, fill=SURF, outline=BORDER, width=1)
        d.ellipse((96, y + 48, 124, y + 76), fill=col)
        d.text((160, y + 26), h, font=F(34), fill=WHITE)
        d.text((160, y + 70), sub, font=F(26, False), fill=GREY)
        y += 138
    img.save(os.path.join(OUT, "ph-03-method.png")); print("ph-03-method.png")

def thumb():
    s = 240; img = Image.new("RGB", (s, s), (24, 24, 27)); d = ImageDraw.Draw(img)
    for r, col in ((104, (245, 158, 11)), (74, (245, 158, 11)), (44, (225, 29, 72))):
        d.ellipse((s//2 - r, s//2 - r, s//2 + r, s//2 + r), outline=col, width=4)
    d.text((s//2, s//2 - 4), "WR", font=F(52), anchor="mm", fill=WHITE)
    img.save(os.path.join(OUT, "ph-thumb.png")); print("ph-thumb.png")

if __name__ == "__main__":
    hero(); ranking(); method(); thumb()
