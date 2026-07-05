#!/usr/bin/env python3
"""Generate SEO landing pages: 'Will AI replace <job>?' — one per high-search-volume job.

Each page targets a long-tail query (e.g. "will ai replace nurses") with genuinely
unique, crawlable content drawn from web/en/jobs.json (per-job task breakdown), plus a
FAQPage schema for rich snippets. Honest by design: scores are hand-estimated directional
references (calibrated:false), never presented as predictions.

Run: python3 gen_seo_pages.py
Idempotent — regenerates web/en/will-ai-replace-*.html and rewrites the sitemap block.
"""
import json, os, html, re, urllib.parse as up

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web", "en")
BASE_URL = "https://idsexyhomme-code.github.io/1000/web/en"
JOBS = json.load(open(os.path.join(WEB, "jobs.json")))

# Curated high-search-volume jobs (canonical keys in jobs.json). One page each.
CURATED = [
    "teacher", "nurse", "doctor", "lawyer", "accountant", "graphic-designer",
    "truck-driver", "cashier", "radiologist", "translator",
    "customer-service-representative", "data-analyst", "financial-analyst",
    "marketer", "sales-rep", "recruiter", "project-manager", "architect",
    "pharmacist", "therapist", "journalist", "photographer", "chef",
    "electrician", "plumber", "real-estate-agent", "insurance-agent",
    "receptionist", "paralegal", "actuary", "auditor", "bookkeeper",
    "copywriter", "ux-designer", "product-manager", "consultant", "professor",
    "pilot", "flight-attendant", "police-officer", "firefighter",
    "social-worker", "psychologist", "editor", "data-scientist",
    "investment-banker", "veterinarian", "optometrist", "surgeon",
    "senior-developer", "frontend-developer", "content-writer",
]

def band(score):
    if score < 25:  return ("Clear", "Low", "var(--color-clear)", "#3b82f6")
    if score < 45:  return ("Partly cloudy", "Moderate", "var(--color-pcloudy)", "#8b5cf6")
    if score < 65:  return ("Cloudy", "Elevated", "var(--color-cloudy)", "#f59e0b")
    return ("Storm", "High", "var(--color-typhoon)", "#e11d48")

def plural(name):
    # naive but fine for these nouns
    n = name
    if n.endswith("y") and n[-2:-1].lower() not in "aeiou": return n[:-1] + "ies"
    if n.endswith(("s","x","ch","sh")): return n + "es"
    return n + "s"

def esc(s): return html.escape(s, quote=True)

def bar_color(v):
    if v >= 65: return "linear-gradient(90deg,#9f1239,#fb7185)"
    if v >= 45: return "linear-gradient(90deg,#b45309,#f59e0b)"
    if v >= 25: return "linear-gradient(90deg,#5b21b6,#8b5cf6)"
    return "linear-gradient(90deg,#1d4ed8,#3b82f6)"

def page(key):
    j = JOBS[key]
    name = j["name"]; emoji = j.get("emoji", "🧭"); score = j["base"]
    pl = plural(name); pl_l = pl.lower(); name_l = name.lower()
    bname, blevel, bvar, bhex = band(score)
    hi = j.get("hi", []); lo = j.get("lo", [])
    needle = round(1.8 * score, 2)
    url = f"{BASE_URL}/will-ai-replace-{key}.html"
    title = f"Will AI Replace {pl}? Task-by-Task AI Risk (2026)"
    desc = (f"Will AI replace {pl_l}? A task-level breakdown of AI exposure for {name_l} work "
            f"— estimated AI-pressure {score}/100 ({bname}). Honest method, sources, free 1-min test.")

    # task rows (hi = most exposed, lo = hardest to automate)
    rows = ""
    for label, v in hi + lo:
        rows += (f'<div class="task-item"><div class="task-label">{esc(label)}</div>'
                 f'<div class="task-track"><div class="task-bar" style="width:{v}%;background:{bar_color(v)}"></div></div>'
                 f'<div class="task-value">{v}</div></div>\n')

    hi_txt = ", ".join(esc(l.lower()) for l, _ in hi[:3]) or "routine, repeatable tasks"
    lo_txt = ", ".join(esc(l.lower()) for l, _ in lo[:2]) or "judgment-heavy, human-facing work"

    short_answer = (
        f"Not wholesale — at least not in the near term. On a task-level view, {name_l} work "
        f"carries an estimated <b>AI-pressure of {score}/100 ({bname.lower()})</b>. The parts under "
        f"the most automation pressure are <b>{hi_txt}</b>. The parts that anchor the role — hardest "
        f"for AI to take — are <b>{lo_txt}</b>. So the realistic near-term story is <b>task reshuffling, "
        f"not job deletion</b>: the routine slices shrink, the judgment slices become the job.")

    # FAQ (visible + schema)
    faqs = [
        (f"Will AI replace {pl_l}?",
         f"Based on WorkRadar's task-level estimate, {name_l} work sits at {score}/100 AI-pressure "
         f"({bname.lower()}). That points to parts of the role being automated or accelerated rather than "
         f"the whole job disappearing soon. The most exposed tasks are {hi_txt}."),
        (f"Which {name_l} tasks are most at risk from AI?",
         f"The highest-exposure tasks in our breakdown are {hi_txt}. These are the repeatable, "
         f"well-specified parts where current AI tools are strongest."),
        (f"How can {pl_l} stay relevant as AI advances?",
         f"Lean into the lowest-exposure parts of the role — {lo_txt} — and use AI to clear the routine "
         f"work so your time shifts toward judgment, relationships, and accountability. Run the free "
         f"1-minute WorkRadar test to see the exposure on your exact task mix."),
    ]
    faq_html = ""
    for q, a in faqs:
        faq_html += f'<details class="faq"><summary>{esc(q)}</summary><p>{a}</p></details>\n'
    faq_schema = {"@context": "https://schema.org", "@type": "FAQPage",
                  "mainEntity": [{"@type": "Question", "name": q,
                                  "acceptedAnswer": {"@type": "Answer", "text": re.sub("<[^>]+>", "", a)}}
                                 for q, a in faqs]}

    # share bar (X / LinkedIn / copy) — social distribution signal
    share_text = f"Will AI replace {pl_l}? {name} work scores {score}/100 AI-pressure ({bname}) — task-by-task, with sources."
    x_url = "https://twitter.com/intent/tweet?text=" + up.quote(share_text) + "&url=" + up.quote(url)
    li_url = "https://www.linkedin.com/sharing/share-offsite/?url=" + up.quote(url)
    share_html = (f'<div class="share-bar"><span class="share-lbl">Share:</span>'
                  f'<a class="sbtn" href="{x_url}" target="_blank" rel="noopener" aria-label="Share on X">𝕏</a>'
                  f'<a class="sbtn" href="{li_url}" target="_blank" rel="noopener" aria-label="Share on LinkedIn">in</a>'
                  f'<button class="sbtn" type="button" onclick="wrCopy(this)">Copy link</button></div>')

    # related internal links (next 6 in curated order, wrap around)
    idx = CURATED.index(key)
    rel = [k for k in (CURATED[idx+1:] + CURATED[:idx]) if k in JOBS][:6]
    rel_html = "".join(
        f'<a class="rel" href="will-ai-replace-{k}.html">Will AI replace {esc(plural(JOBS[k]["name"]).lower())}?</a>'
        for k in rel)

    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — WorkRadar</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="article"><meta property="og:site_name" content="WorkRadar">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE_URL}/og.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}"><meta name="twitter:image" content="{BASE_URL}/og.png">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='88'%3E%F0%9F%93%A1%3C/text%3E%3C/svg%3E">
<script type="application/ld+json">{json.dumps(faq_schema, ensure_ascii=False)}</script>
<style>
:root{{--bg-base:#09090b;--bg-surface:#18181b;--bg-elevate:#27272a;--text-primary:#fafafa;--text-secondary:#a1a1aa;--text-tertiary:#8b8b94;--color-clear:#3b82f6;--color-pcloudy:#8b5cf6;--color-cloudy:#f59e0b;--color-typhoon:#e11d48;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#000;color:var(--text-primary);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,Helvetica,Arial,sans-serif;display:flex;justify-content:center;line-height:1.6;}}
.wrap{{width:100%;max-width:640px;background:var(--bg-base);min-height:100vh;padding:28px 20px 56px;}}
.crumb{{font-size:12px;color:var(--text-tertiary);margin-bottom:18px;}}
.crumb a{{color:var(--text-secondary);text-decoration:none;}}
h1{{font-size:29px;font-weight:800;letter-spacing:-.7px;line-height:1.18;margin-bottom:14px;}}
.lead{{font-size:16px;color:var(--text-secondary);margin-bottom:26px;}}
.gauge-wrapper{{position:relative;width:100%;max-width:280px;margin:0 auto 26px;}}
.gauge-svg{{width:100%;height:auto;overflow:visible;}}
.answer{{background:linear-gradient(145deg,#18181b,#131316);border:1px solid var(--bg-elevate);border-radius:18px;padding:22px 20px;margin-bottom:32px;font-size:16px;}}
.answer b{{color:#fff;}}
h2{{font-size:20px;font-weight:700;letter-spacing:-.4px;margin:34px 0 16px;}}
.task-item{{display:flex;align-items:center;margin-bottom:13px;}}
.task-label{{width:150px;font-size:13.5px;color:var(--text-secondary);}}
.task-track{{flex:1;height:8px;background:var(--bg-elevate);border-radius:4px;margin:0 12px;position:relative;overflow:hidden;}}
.task-bar{{position:absolute;inset:0 auto 0 0;border-radius:4px;}}
.task-value{{width:30px;text-align:right;font-size:14px;font-weight:600;}}
.faq{{background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:12px;padding:14px 16px;margin-bottom:10px;}}
.faq summary{{font-size:15.5px;font-weight:600;cursor:pointer;letter-spacing:-.2px;}}
.faq p{{font-size:14.5px;color:var(--text-secondary);margin-top:10px;}}
.cta{{background:linear-gradient(145deg,rgba(245,158,11,.08),rgba(225,29,72,.03));border:1px solid rgba(245,158,11,.2);border-radius:20px;padding:28px 22px;text-align:center;margin:36px 0;}}
.cta h2{{margin-top:0;}}
.cta-btn{{display:inline-block;background:var(--text-primary);color:#000;padding:15px 30px;border-radius:30px;font-size:16px;font-weight:800;text-decoration:none;margin-top:6px;}}
.rel{{display:block;background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:12px;padding:13px 16px;margin-bottom:9px;font-size:14.5px;font-weight:600;color:var(--text-primary);text-decoration:none;letter-spacing:-.2px;}}
.rel:hover{{border-color:var(--color-cloudy);}}
.share-bar{{display:flex;align-items:center;gap:8px;margin:8px 0 4px;flex-wrap:wrap;}}
.share-lbl{{font-size:13px;color:var(--text-tertiary);}}
.sbtn{{display:inline-flex;align-items:center;justify-content:center;min-width:40px;height:36px;padding:0 14px;background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:10px;color:var(--text-primary);font-size:14px;font-weight:700;text-decoration:none;cursor:pointer;font-family:inherit;}}
.sbtn:hover{{border-color:var(--color-cloudy);}}
.foot{{font-size:12px;color:var(--text-tertiary);line-height:1.7;margin-top:36px;border-top:1px solid var(--bg-elevate);padding-top:20px;}}
.foot b{{color:var(--text-secondary);}}
.foot a{{color:var(--text-secondary);}}
</style></head><body><div class="wrap">
<nav class="crumb"><a href="index.html">WorkRadar</a> › Will AI replace {esc(pl_l)}?</nav>
<h1>Will AI replace {esc(pl_l)}? {emoji}</h1>
<p class="lead">A task-by-task look at how exposed {esc(name_l)} work is to AI — estimated AI-pressure <b style="color:{bhex}">{score}/100 ({bname})</b>. Not a prediction. A directional reference from a fixed, published method.</p>
<div class="gauge-wrapper"><svg class="gauge-svg" viewBox="0 0 200 110" role="img" aria-label="AI pressure reference index {score} out of 100, {bname}"><path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#27272a" stroke-width="12" stroke-linecap="round"/><path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="var(--color-clear)" stroke-width="12" stroke-dasharray="62.83 502.65"/><path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="var(--color-pcloudy)" stroke-width="12" stroke-dasharray="62.83 502.65" stroke-dashoffset="-62.83"/><path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="var(--color-cloudy)" stroke-width="12" stroke-dasharray="62.83 502.65" stroke-dashoffset="-125.66"/><path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="var(--color-typhoon)" stroke-width="12" stroke-dasharray="62.83 502.65" stroke-dashoffset="-188.49"/><g transform="rotate({needle}, 100, 100)"><circle cx="20" cy="100" r="6" fill="#fff" stroke="#18181b" stroke-width="2.5"/></g><text x="100" y="72" font-size="42" font-weight="800" text-anchor="middle" fill="#fff" letter-spacing="-1">{score}</text><text x="100" y="90" font-size="11" font-weight="500" text-anchor="middle" fill="var(--text-tertiary)">AI pressure · {bname}</text></svg></div>
<div class="answer"><b>The short answer.</b> {short_answer}</div>
<h2>📊 {esc(name)} tasks by AI pressure</h2>
{rows}<p style="font-size:12.5px;color:var(--text-tertiary);margin-top:10px;">Higher = more exposed to current AI tools. Values are directional estimates, not measured probabilities.</p>
<div class="cta"><h2>See the pressure on <em>your</em> exact tasks</h2>
<p class="lead" style="margin-bottom:8px;">This page shows the role in general. The free 1-minute test scores <b>your</b> specific task mix — with linked sources.</p>
<a class="cta-btn" href="index.html">Take the free AI Risk test →</a></div>
{share_html}
<h2>❓ {esc(name)} &amp; AI — FAQ</h2>
{faq_html}<h2>Related: will AI replace…</h2>
{rel_html}<p class="foot">※ <b>WorkRadar AI-pressure</b> is a directional reference indicator built from public AI news and task analysis with a fixed, published method — <b>not a prediction</b>, and not a verdict on any person. Scores are hand-estimated (uncalibrated) and shown to illustrate relative exposure. See the <a href="index.html">method</a>, <a href="privacy.html">privacy</a> &amp; <a href="terms.html">terms</a>.</p>
</div>
<script>
function wrCopy(b){{var u=location.href;if(navigator.clipboard){{navigator.clipboard.writeText(u).then(function(){{b.textContent='Copied!';setTimeout(function(){{b.textContent='Copy link';}},1500);}});}}else{{window.prompt('Copy link',u);}}}}
</script>
<script data-goatcounter="https://workradar.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
</body></html>"""

def main():
    made = []
    for key in CURATED:
        if key not in JOBS:
            print("SKIP (missing key):", key); continue
        out = os.path.join(WEB, f"will-ai-replace-{key}.html")
        open(out, "w").write(page(key))
        made.append(key)
    print(f"Generated {len(made)} pages.")

    # rewrite sitemap.xml
    core = [
        ("", "1.0", "weekly"), ("ranked.html", "0.8", "weekly"),
        ("daily.html", "0.7", "daily"), ("game.html", "0.6", "weekly"),
        ("reels.html", "0.5", "weekly"), ("privacy.html", "0.3", "yearly"),
        ("terms.html", "0.3", "yearly"),
    ]
    lastmod = "2026-07-05"
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, pri, freq in core:
        lines.append(f'  <url><loc>{BASE_URL}/{path}</loc><lastmod>{lastmod}</lastmod><changefreq>{freq}</changefreq><priority>{pri}</priority></url>')
    for key in made:
        lines.append(f'  <url><loc>{BASE_URL}/will-ai-replace-{key}.html</loc><lastmod>{lastmod}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>')
    lines.append('</urlset>')
    open(os.path.join(WEB, "sitemap.xml"), "w").write("\n".join(lines) + "\n")
    print("Sitemap rewritten with", len(core) + len(made), "urls.")

    # robots.txt (best-effort; subpath sites: also submit sitemap in Search Console)
    open(os.path.join(WEB, "robots.txt"), "w").write(
        "User-agent: *\nAllow: /\n\nSitemap: " + BASE_URL + "/sitemap.xml\n")
    print("robots.txt written.")

if __name__ == "__main__":
    main()
