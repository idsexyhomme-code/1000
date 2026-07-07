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

# Recognizable, high-search-volume occupations (canonical keys in jobs.json).
# One landing page each. All verified to carry unique per-job task data (not thin).
CURATED = [
    "data-entry-clerk", "cashier", "bookkeeper", "receptionist", "proofreader",
    "paralegal", "translator", "transcriptionist", "customer-service-representative",
    "call-center-agent", "accountant", "tax-preparer", "travel-agent", "loan-officer",
    "claims-adjuster", "copywriter", "content-writer", "junior-developer",
    "senior-developer", "frontend-developer", "web-developer", "data-analyst",
    "financial-analyst", "graphic-designer", "ui-designer", "ux-designer",
    "video-editor", "photographer", "journalist", "editor", "marketer",
    "digital-marketer", "social-media-manager", "seo-specialist", "recruiter",
    "hr-manager", "project-manager", "product-manager", "business-analyst",
    "consultant", "sales-rep", "real-estate-agent", "insurance-agent", "stockbroker",
    "financial-advisor", "actuary", "auditor", "lawyer", "teacher", "professor",
    "tutor", "librarian", "nurse", "doctor", "surgeon", "pharmacist", "radiologist",
    "veterinarian", "physical-therapist", "psychologist", "therapist", "social-worker",
    "chef", "bartender", "barista", "baker", "truck-driver", "delivery-driver",
    "pilot", "flight-attendant", "police-officer", "firefighter", "security-guard",
    "electrician", "plumber", "carpenter", "welder", "mechanic", "architect",
    "civil-engineer", "mechanical-engineer", "electrical-engineer", "data-scientist",
    "ml-engineer", "devops-engineer", "cybersecurity-analyst", "it-support",
    "optometrist", "dietitian", "makeup-artist", "interior-designer",
    "fashion-designer", "musician", "actor", "animator", "game-designer",
    "ux-researcher", "investment-banker", "management-consultant", "office-manager",
    "executive-assistant", "administrative-assistant",
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
<script type="application/ld+json">{breadcrumb_ld("Will AI replace " + pl_l + "?", url)}</script>
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
.rankline{{font-size:13px;color:var(--text-tertiary);margin:18px 0 4px;line-height:1.7;}}
.rankline a{{color:var(--text-secondary);}}
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
<p class="rankline">📊 Full ranking: <a href="most-at-risk-jobs-from-ai.html">jobs most at risk from AI</a> · <a href="safest-jobs-from-ai.html">safest jobs from AI</a> · <a href="methodology.html">how we score</a></p>
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

LISTICLES = {
    "most-at-risk-jobs-from-ai": {
        "mode": "risk", "n": 25, "emoji": "🌪️",
        "h1": "Jobs Most at Risk From AI (2026)",
        "title": "Jobs Most at Risk From AI (2026): 25 Careers, Ranked by Task Exposure",
        "desc": "Which jobs are most at risk from AI in 2026? 25 common careers ranked by task-level AI exposure — data entry, transcription, customer service and more. Honest method, free 1-min test.",
        "intro": "These are the common jobs where the most of the day-to-day work is exposed to current AI tools. Ranking is by <b>task-level AI-pressure</b> — how much of the role is repeatable, well-specified work that today's AI does well. It's a directional reference, not a prediction: high exposure means tasks get reshuffled and automated, not that the job vanishes overnight.",
        "og": "og-most-at-risk.png",
        "other": ("safest-jobs-from-ai", "🛡️ See the safest jobs from AI →"),
    },
    "safest-jobs-from-ai": {
        "mode": "safe", "n": 25, "emoji": "🛡️",
        "h1": "Safest Jobs From AI (2026)",
        "title": "Safest Jobs From AI (2026): 25 Most AI-Resilient Careers, Ranked",
        "desc": "What are the safest jobs from AI in 2026? 25 of the most AI-resilient common careers ranked by how little of the work AI can do — trades, care, hands-on and judgment roles. Honest method, free test.",
        "intro": "These are the common jobs where the <b>least</b> of the day-to-day work is exposed to current AI — hands-on trades, physical care, live human judgment, and high-stakes accountability. Often called “AI-proof,” but no job is fully immune; think <b>most resilient</b>. Ranking is by task-level AI-pressure (lower = more resilient), a directional reference, not a prediction.",
        "og": "og-safest.png",
        "other": ("most-at-risk-jobs-from-ai", "🌪️ See the jobs most at risk from AI →"),
    },
}

def listicle(slug):
    cfg = LISTICLES[slug]
    ranked = sorted(((k, JOBS[k]["name"], JOBS[k]["base"]) for k in CURATED if k in JOBS),
                    key=lambda x: -x[2] if cfg["mode"] == "risk" else x[2])[:cfg["n"]]
    url = f"{BASE_URL}/{slug}.html"
    rows = ""
    items = []
    for i, (k, name, score) in enumerate(ranked, 1):
        bname, blevel, bvar, bhex = band(score)
        rows += (f'<a class="lrow" href="will-ai-replace-{k}.html">'
                 f'<span class="lrk">{i}</span>'
                 f'<span class="lem">{JOBS[k].get("emoji","🧭")}</span>'
                 f'<span class="lnm">{esc(name)}</span>'
                 f'<span class="lbar"><span class="lbf" style="width:{score}%;background:{bhex}"></span></span>'
                 f'<span class="lv" style="color:{bhex}">{score}</span></a>\n')
        items.append({"@type": "ListItem", "position": i, "name": name, "url": f"{BASE_URL}/will-ai-replace-{k}.html"})
    schema = {"@context": "https://schema.org", "@type": "ItemList",
              "name": cfg["h1"], "itemListOrder": "https://schema.org/ItemListOrderDescending"
              if cfg["mode"] == "risk" else "https://schema.org/ItemListOrderAscending",
              "numberOfItems": len(items), "itemListElement": items}
    other_slug, other_label = cfg["other"]
    share_text = f"{cfg['h1']} — {ranked[0][1]} tops the list. See where your job lands on WorkRadar."
    x_url = "https://twitter.com/intent/tweet?text=" + up.quote(share_text) + "&url=" + up.quote(url)
    li_url = "https://www.linkedin.com/sharing/share-offsite/?url=" + up.quote(url)
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(cfg['title'])} — WorkRadar</title>
<meta name="description" content="{esc(cfg['desc'])}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="article"><meta property="og:site_name" content="WorkRadar">
<meta property="og:title" content="{esc(cfg['title'])}">
<meta property="og:description" content="{esc(cfg['desc'])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE_URL}/{cfg['og']}">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(cfg['title'])}"><meta name="twitter:image" content="{BASE_URL}/{cfg['og']}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='88'%3E%F0%9F%93%A1%3C/text%3E%3C/svg%3E">
<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>
<script type="application/ld+json">{breadcrumb_ld(cfg['h1'], url)}</script>
<style>
:root{{--bg-base:#09090b;--bg-surface:#18181b;--bg-elevate:#27272a;--text-primary:#fafafa;--text-secondary:#a1a1aa;--text-tertiary:#8b8b94;--color-clear:#3b82f6;--color-pcloudy:#8b5cf6;--color-cloudy:#f59e0b;--color-typhoon:#e11d48;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#000;color:var(--text-primary);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,Helvetica,Arial,sans-serif;display:flex;justify-content:center;line-height:1.6;}}
.wrap{{width:100%;max-width:640px;background:var(--bg-base);min-height:100vh;padding:28px 20px 56px;}}
.crumb{{font-size:12px;color:var(--text-tertiary);margin-bottom:18px;}}
.crumb a{{color:var(--text-secondary);text-decoration:none;}}
h1{{font-size:29px;font-weight:800;letter-spacing:-.7px;line-height:1.18;margin-bottom:14px;}}
.lead{{font-size:16px;color:var(--text-secondary);margin-bottom:24px;}}
.lrow{{display:flex;align-items:center;gap:11px;padding:11px 13px;border-radius:12px;background:#131316;border:1px solid #1f1f23;margin-bottom:7px;text-decoration:none;color:var(--text-primary);}}
.lrow:hover{{border-color:var(--color-cloudy);}}
.lrk{{width:26px;font-size:13px;font-weight:800;color:var(--text-tertiary);text-align:center;flex-shrink:0;}}
.lem{{font-size:21px;flex-shrink:0;}}
.lnm{{flex:1;font-size:14.5px;font-weight:600;letter-spacing:-.2px;}}
.lbar{{width:72px;height:7px;background:var(--bg-elevate);border-radius:4px;overflow:hidden;flex-shrink:0;}}
.lbf{{display:block;height:100%;border-radius:4px;}}
.lv{{width:26px;text-align:right;font-size:13px;font-weight:800;flex-shrink:0;}}
h2{{font-size:20px;font-weight:700;letter-spacing:-.4px;margin:34px 0 16px;}}
.cta{{background:linear-gradient(145deg,rgba(245,158,11,.08),rgba(225,29,72,.03));border:1px solid rgba(245,158,11,.2);border-radius:20px;padding:26px 22px;text-align:center;margin:32px 0;}}
.cta-btn{{display:inline-block;background:var(--text-primary);color:#000;padding:15px 30px;border-radius:30px;font-size:16px;font-weight:800;text-decoration:none;margin-top:6px;}}
.other{{display:block;background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:14px;padding:16px;text-align:center;font-size:15px;font-weight:700;color:var(--text-primary);text-decoration:none;margin-bottom:10px;}}
.other:hover{{border-color:var(--color-cloudy);}}
.share-bar{{display:flex;align-items:center;gap:8px;margin:20px 0 4px;flex-wrap:wrap;}}
.share-lbl{{font-size:13px;color:var(--text-tertiary);}}
.sbtn{{display:inline-flex;align-items:center;justify-content:center;min-width:40px;height:36px;padding:0 14px;background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:10px;color:var(--text-primary);font-size:14px;font-weight:700;text-decoration:none;cursor:pointer;font-family:inherit;}}
.sbtn:hover{{border-color:var(--color-cloudy);}}
.foot{{font-size:12px;color:var(--text-tertiary);line-height:1.7;margin-top:34px;border-top:1px solid var(--bg-elevate);padding-top:20px;}}
.foot b{{color:var(--text-secondary);}}
.foot a{{color:var(--text-secondary);}}
</style></head><body><div class="wrap">
<nav class="crumb"><a href="index.html">WorkRadar</a> › {esc(cfg['h1'])}</nav>
<h1>{cfg['emoji']} {esc(cfg['h1'])}</h1>
<p class="lead">{cfg['intro']}</p>
<div class=" list">{rows}</div>
<p style="font-size:12.5px;color:var(--text-tertiary);margin-top:10px;">Score = task-level AI-pressure (0–100). Ranked among {len(CURATED)} common occupations we track. Directional estimates, not measured probabilities. Tap any job for its task breakdown.</p>
<div class="cta"><h2 style="margin-top:0">Where does <em>your</em> job land?</h2>
<p class="lead" style="margin-bottom:8px;">This list ranks roles in general. The free 1-minute test scores <b>your</b> exact task mix — with sources.</p>
<a class="cta-btn" href="index.html">Take the free AI Risk test →</a></div>
<a class="other" href="{other_slug}.html">{esc(other_label)}</a>
<div class="share-bar"><span class="share-lbl">Share:</span>
<a class="sbtn" href="{x_url}" target="_blank" rel="noopener" aria-label="Share on X">𝕏</a>
<a class="sbtn" href="{li_url}" target="_blank" rel="noopener" aria-label="Share on LinkedIn">in</a>
<button class="sbtn" type="button" onclick="wrCopy(this)">Copy link</button></div>
<p class="foot">※ <b>WorkRadar AI-pressure</b> is a directional reference indicator built from public AI news and task analysis with a fixed, published method — <b>not a prediction</b>, and not a verdict on any person. Scores are hand-estimated (uncalibrated). See the <a href="index.html">method</a>, <a href="privacy.html">privacy</a> &amp; <a href="terms.html">terms</a>.</p>
</div>
<script>
function wrCopy(b){{var u=location.href;if(navigator.clipboard){{navigator.clipboard.writeText(u).then(function(){{b.textContent='Copied!';setTimeout(function(){{b.textContent='Copy link';}},1500);}});}}else{{window.prompt('Copy link',u);}}}}
</script>
<script data-goatcounter="https://workradar.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
</body></html>"""

def breadcrumb_ld(leaf_name, leaf_url):
    return json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "WorkRadar", "item": f"{BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": leaf_name, "item": leaf_url}]},
        ensure_ascii=False)

CLUSTERS = {
    "healthcare": {"emoji": "🩺", "label": "healthcare jobs",
        "jobs": ["nurse","doctor","surgeon","pharmacist","radiologist","veterinarian","physical-therapist","psychologist","therapist","dietitian","optometrist","social-worker"],
        "intro": "Healthcare splits sharply. Documentation, coding, scheduling and image triage face real AI pressure — but hands-on care, physical exams and live clinical judgment are among the hardest work for AI to touch. Here's how common healthcare roles rank by task exposure."},
    "tech-and-software": {"emoji": "💻", "label": "tech & software jobs",
        "jobs": ["junior-developer","senior-developer","frontend-developer","web-developer","data-scientist","ml-engineer","devops-engineer","cybersecurity-analyst","it-support","data-analyst","ux-designer","ui-designer","ux-researcher","product-manager","game-designer"],
        "intro": "Software is being reshaped from the inside. Boilerplate, tests and simple fixes are increasingly AI-assisted, while architecture, debugging gnarly systems and product judgment hold their value. Here's how tech roles rank by task exposure."},
    "finance-and-accounting": {"emoji": "💰", "label": "finance & accounting jobs",
        "jobs": ["accountant","bookkeeper","tax-preparer","financial-analyst","financial-advisor","actuary","auditor","investment-banker","stockbroker","loan-officer","claims-adjuster","insurance-agent"],
        "intro": "Finance runs on structured, rule-based work — exactly what AI does well. Data entry, reconciliation, tax prep and first-pass analysis are highly exposed; relationship, fiduciary and edge-case judgment less so. Here's the ranking."},
    "creative-and-media": {"emoji": "🎨", "label": "creative & media jobs",
        "jobs": ["graphic-designer","video-editor","photographer","copywriter","content-writer","journalist","editor","animator","musician","actor","makeup-artist","interior-designer","fashion-designer","social-media-manager","digital-marketer","marketer","seo-specialist"],
        "intro": "Creative work is being unbundled. Production tasks — first drafts, cutdowns, stock-style output — face heavy AI pressure, while taste, original concept and client trust stay human. Here's how media roles rank."},
    "business-and-admin": {"emoji": "📊", "label": "business & admin jobs",
        "jobs": ["project-manager","business-analyst","consultant","management-consultant","hr-manager","recruiter","office-manager","executive-assistant","administrative-assistant","sales-rep","real-estate-agent","lawyer","paralegal"],
        "intro": "Business, admin and professional-services roles carry a lot of coordinable, document-heavy work that AI accelerates — scheduling, reporting, first-pass drafting and analysis — while stakeholder judgment and accountability stay human. Here's the ranking."},
    "office-and-support": {"emoji": "🗂️", "label": "office & support jobs",
        "jobs": ["data-entry-clerk","cashier","receptionist","customer-service-representative","call-center-agent","proofreader","transcriptionist","translator","travel-agent"],
        "intro": "Office and support roles sit at the sharp end of AI exposure: much of the work is repeatable, well-specified and text-based — exactly what current AI does best. Here's how these roles rank, most exposed first."},
    "skilled-trades": {"emoji": "🔧", "label": "skilled trade jobs",
        "jobs": ["electrician","plumber","carpenter","welder","mechanic"],
        "intro": "Skilled trades are among the most AI-resilient work there is. Physical, on-site, judgment-in-the-moment tasks resist automation — though estimating and scheduling see some pressure. Here's how the trades rank."},
    "education": {"emoji": "📚", "label": "education jobs",
        "jobs": ["teacher","professor","tutor","librarian"],
        "intro": "Teaching's routine layers — lesson drafts, grading, content — are increasingly AI-assisted, but the human core (motivation, classroom management, mentoring) is hard to automate. Here's how education roles rank."},
    "transportation-and-safety": {"emoji": "🚚", "label": "transportation & safety jobs",
        "jobs": ["truck-driver","delivery-driver","pilot","flight-attendant","police-officer","firefighter","security-guard"],
        "intro": "Transportation and safety work is largely physical and situational — hard for today's AI, though routing and monitoring see some pressure. Here's how these roles rank by task exposure."},
    "engineering": {"emoji": "📐", "label": "engineering jobs",
        "jobs": ["architect","civil-engineer","mechanical-engineer","electrical-engineer"],
        "intro": "Engineering blends automatable analysis with irreducible judgment. Drafting, calculations and first-pass design see AI pressure; accountability, site reality and novel problems don't. Here's the ranking."},
    "food-and-hospitality": {"emoji": "🍳", "label": "food & hospitality jobs",
        "jobs": ["chef","bartender","barista","baker"],
        "intro": "Food and hospitality is hands-on, physical and social — among the most AI-resilient work. Here's how these roles rank by task exposure."},
}

def cluster_page(slug):
    cfg = CLUSTERS[slug]
    label = cfg["label"]; label_t = label[0].upper() + label[1:]
    ranked = sorted(((k, JOBS[k]["name"], JOBS[k]["base"]) for k in cfg["jobs"] if k in JOBS),
                    key=lambda x: -x[2])
    url = f"{BASE_URL}/ai-{slug}-jobs.html"
    title = f"Will AI Replace {label.title()}? (2026) — {len(ranked)} Roles Ranked"
    desc = f"Will AI replace {label}? {len(ranked)} common {label} ranked by task-level AI exposure, most exposed first. Honest method, free 1-minute test."
    rows, items = "", []
    for i, (k, name, score) in enumerate(ranked, 1):
        _, _, _, bhex = band(score)
        rows += (f'<a class="lrow" href="will-ai-replace-{k}.html"><span class="lrk">{i}</span>'
                 f'<span class="lem">{JOBS[k].get("emoji","🧭")}</span><span class="lnm">{esc(name)}</span>'
                 f'<span class="lbar"><span class="lbf" style="width:{score}%;background:{bhex}"></span></span>'
                 f'<span class="lv" style="color:{bhex}">{score}</span></a>\n')
        items.append({"@type": "ListItem", "position": i, "name": name, "url": f"{BASE_URL}/will-ai-replace-{k}.html"})
    schema = {"@context": "https://schema.org", "@type": "ItemList", "name": title,
              "numberOfItems": len(items), "itemListElement": items}
    share_text = f"Will AI replace {label}? {len(ranked)} roles ranked by task exposure on WorkRadar."
    x_url = "https://twitter.com/intent/tweet?text=" + up.quote(share_text) + "&url=" + up.quote(url)
    li_url = "https://www.linkedin.com/sharing/share-offsite/?url=" + up.quote(url)
    other = "".join(f'<a class="chip" href="ai-{s}-jobs.html">{CLUSTERS[s]["emoji"]} {esc(CLUSTERS[s]["label"])}</a>'
                    for s in CLUSTERS if s != slug)
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — WorkRadar</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="article"><meta property="og:site_name" content="WorkRadar">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}"><meta property="og:image" content="{BASE_URL}/og.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}"><meta name="twitter:image" content="{BASE_URL}/og.png">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='88'%3E%F0%9F%93%A1%3C/text%3E%3C/svg%3E">
<script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>
<script type="application/ld+json">{breadcrumb_ld("Will AI replace " + label + "?", url)}</script>
<style>
:root{{--bg-base:#09090b;--bg-surface:#18181b;--bg-elevate:#27272a;--text-primary:#fafafa;--text-secondary:#a1a1aa;--text-tertiary:#8b8b94;--color-clear:#3b82f6;--color-pcloudy:#8b5cf6;--color-cloudy:#f59e0b;--color-typhoon:#e11d48;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#000;color:var(--text-primary);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,Helvetica,Arial,sans-serif;display:flex;justify-content:center;line-height:1.6;}}
.wrap{{width:100%;max-width:640px;background:var(--bg-base);min-height:100vh;padding:28px 20px 56px;}}
.crumb{{font-size:12px;color:var(--text-tertiary);margin-bottom:18px;}}
.crumb a{{color:var(--text-secondary);text-decoration:none;}}
h1{{font-size:28px;font-weight:800;letter-spacing:-.6px;line-height:1.2;margin-bottom:14px;}}
.lead{{font-size:16px;color:var(--text-secondary);margin-bottom:24px;}}
.lrow{{display:flex;align-items:center;gap:11px;padding:11px 13px;border-radius:12px;background:#131316;border:1px solid #1f1f23;margin-bottom:7px;text-decoration:none;color:var(--text-primary);}}
.lrow:hover{{border-color:var(--color-cloudy);}}
.lrk{{width:26px;font-size:13px;font-weight:800;color:var(--text-tertiary);text-align:center;flex-shrink:0;}}
.lem{{font-size:21px;flex-shrink:0;}}
.lnm{{flex:1;font-size:14.5px;font-weight:600;letter-spacing:-.2px;}}
.lbar{{width:72px;height:7px;background:var(--bg-elevate);border-radius:4px;overflow:hidden;flex-shrink:0;}}
.lbf{{display:block;height:100%;border-radius:4px;}}
.lv{{width:26px;text-align:right;font-size:13px;font-weight:800;flex-shrink:0;}}
h2{{font-size:19px;font-weight:700;letter-spacing:-.4px;margin:32px 0 14px;}}
.cta{{background:linear-gradient(145deg,rgba(245,158,11,.08),rgba(225,29,72,.03));border:1px solid rgba(245,158,11,.2);border-radius:20px;padding:26px 22px;text-align:center;margin:30px 0;}}
.cta-btn{{display:inline-block;background:var(--text-primary);color:#000;padding:15px 30px;border-radius:30px;font-size:16px;font-weight:800;text-decoration:none;margin-top:6px;}}
.chips{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:8px;}}
.chip{{font-size:13px;font-weight:600;color:var(--text-secondary);background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:20px;padding:7px 13px;text-decoration:none;letter-spacing:-.2px;}}
.chip:hover{{border-color:var(--color-cloudy);color:var(--text-primary);}}
.share-bar{{display:flex;align-items:center;gap:8px;margin:22px 0 4px;flex-wrap:wrap;}}
.share-lbl{{font-size:13px;color:var(--text-tertiary);}}
.sbtn{{display:inline-flex;align-items:center;justify-content:center;min-width:40px;height:36px;padding:0 14px;background:var(--bg-surface);border:1px solid var(--bg-elevate);border-radius:10px;color:var(--text-primary);font-size:14px;font-weight:700;text-decoration:none;cursor:pointer;font-family:inherit;}}
.sbtn:hover{{border-color:var(--color-cloudy);}}
.foot{{font-size:12px;color:var(--text-tertiary);line-height:1.7;margin-top:32px;border-top:1px solid var(--bg-elevate);padding-top:18px;}}
.foot b{{color:var(--text-secondary);}} .foot a{{color:var(--text-secondary);}}
</style></head><body><div class="wrap">
<nav class="crumb"><a href="index.html">WorkRadar</a> › Will AI replace {esc(label)}?</nav>
<h1>{cfg['emoji']} Will AI replace {esc(label)}?</h1>
<p class="lead">{cfg['intro']}</p>
<div class="list">{rows}</div>
<p style="font-size:12.5px;color:var(--text-tertiary);margin-top:10px;">Score = task-level AI-pressure (0–100), most exposed first. Directional estimates, not measured probabilities. Tap any role for its task breakdown.</p>
<div class="cta"><h2 style="margin-top:0">Where does <em>your</em> job land?</h2>
<p class="lead" style="margin-bottom:8px;">The free 1-minute test scores <b>your</b> exact task mix — with sources.</p>
<a class="cta-btn" href="index.html">Take the free AI Risk test →</a></div>
<h2>Compare across all jobs</h2>
<div class="chips"><a class="chip" href="most-at-risk-jobs-from-ai.html">🌪️ Most at risk</a><a class="chip" href="safest-jobs-from-ai.html">🛡️ Safest</a><a class="chip" href="methodology.html">📋 Method</a></div>
<h2>Other industries</h2>
<div class="chips">{other}</div>
<div class="share-bar"><span class="share-lbl">Share:</span>
<a class="sbtn" href="{x_url}" target="_blank" rel="noopener" aria-label="Share on X">𝕏</a>
<a class="sbtn" href="{li_url}" target="_blank" rel="noopener" aria-label="Share on LinkedIn">in</a>
<button class="sbtn" type="button" onclick="wrCopy(this)">Copy link</button></div>
<p class="foot">※ <b>WorkRadar AI-pressure</b> is a directional reference indicator built from public AI news and task analysis with a fixed, published method — <b>not a prediction</b>, and not a verdict on any person. Scores are hand-estimated (uncalibrated). See the <a href="methodology.html">method</a>, <a href="privacy.html">privacy</a> &amp; <a href="terms.html">terms</a>.</p>
</div>
<script>
function wrCopy(b){{var u=location.href;if(navigator.clipboard){{navigator.clipboard.writeText(u).then(function(){{b.textContent='Copied!';setTimeout(function(){{b.textContent='Copy link';}},1500);}});}}else{{window.prompt('Copy link',u);}}}}
</script>
<script data-goatcounter="https://workradar.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
</body></html>"""

def build_hub_footer():
    links = "".join(
        f'<a href="will-ai-replace-{k}.html">Will AI replace {esc(plural(JOBS[k]["name"]).lower())}?</a>'
        for k in CURATED if k in JOBS)
    clusters = "".join(
        f'<a href="ai-{s}-jobs.html">{CLUSTERS[s]["emoji"]} {esc(CLUSTERS[s]["label"][0].upper() + CLUSTERS[s]["label"][1:])}</a>'
        for s in CLUSTERS)
    return ('<footer class="seo-hub"><h2>Will AI replace your job? Browse by role</h2>'
            '<p class="seo-top"><a href="most-at-risk-jobs-from-ai.html">🌪️ Jobs most at risk from AI</a>'
            '<a href="safest-jobs-from-ai.html">🛡️ Safest jobs from AI</a></p>'
            f'<nav class="seo-top">{clusters}</nav>'
            f'<nav class="seo-links">{links}</nav>'
            '<p class="seo-fine">Directional AI-exposure references built from public AI news with a fixed, '
            'published method — <b>not predictions</b>. <a href="methodology.html">Method</a> · '
            '<a href="privacy.html">Privacy</a> · <a href="terms.html">Terms</a></p></footer>')

def main():
    made = []
    for key in CURATED:
        if key not in JOBS:
            print("SKIP (missing key):", key); continue
        out = os.path.join(WEB, f"will-ai-replace-{key}.html")
        open(out, "w").write(page(key))
        made.append(key)
    print(f"Generated {len(made)} pages.")

    # data-driven listicles (high-volume "most at risk / safest jobs from AI" queries)
    for slug in LISTICLES:
        open(os.path.join(WEB, f"{slug}.html"), "w").write(listicle(slug))
    print(f"Generated {len(LISTICLES)} listicles.")

    # industry cluster hubs ("will AI replace <industry> jobs?" + internal-link pillars)
    for slug in CLUSTERS:
        open(os.path.join(WEB, f"ai-{slug}-jobs.html"), "w").write(cluster_page(slug))
    print(f"Generated {len(CLUSTERS)} industry cluster hubs.")

    # rewrite sitemap.xml
    core = [
        ("", "1.0", "weekly"), ("methodology.html", "0.7", "monthly"),
        ("ranked.html", "0.8", "weekly"),
        ("daily.html", "0.7", "daily"), ("game.html", "0.6", "weekly"),
        ("reels.html", "0.5", "weekly"), ("privacy.html", "0.3", "yearly"),
        ("terms.html", "0.3", "yearly"),
    ]
    listicle_urls = [(f"{s}.html", "0.9", "weekly") for s in LISTICLES]
    cluster_urls = [(f"ai-{s}-jobs.html", "0.8", "weekly") for s in CLUSTERS]
    lastmod = "2026-07-07"
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, pri, freq in core + listicle_urls + cluster_urls:
        lines.append(f'  <url><loc>{BASE_URL}/{path}</loc><lastmod>{lastmod}</lastmod><changefreq>{freq}</changefreq><priority>{pri}</priority></url>')
    for key in made:
        lines.append(f'  <url><loc>{BASE_URL}/will-ai-replace-{key}.html</loc><lastmod>{lastmod}</lastmod><changefreq>monthly</changefreq><priority>0.7</priority></url>')
    lines.append('</urlset>')
    open(os.path.join(WEB, "sitemap.xml"), "w").write("\n".join(lines) + "\n")
    print("Sitemap rewritten with", len(core) + len(listicle_urls) + len(cluster_urls) + len(made), "urls.")

    # robots.txt (best-effort; subpath sites: also submit sitemap in Search Console)
    open(os.path.join(WEB, "robots.txt"), "w").write(
        "User-agent: *\nAllow: /\n\nSitemap: " + BASE_URL + "/sitemap.xml\n")
    print("robots.txt written.")

    # regenerate index.html internal-link hub in place (drift-free)
    idx_path = os.path.join(WEB, "index.html")
    idx = open(idx_path, encoding="utf-8").read()
    new_idx, n = re.subn(r'<footer class="seo-hub">.*?</footer>', build_hub_footer(), idx, flags=re.S)
    if n == 1:
        open(idx_path, "w").write(new_idx)
        print("index.html hub footer regenerated.")
    else:
        print(f"WARN: hub footer not updated (matched {n}) — check index.html")

if __name__ == "__main__":
    main()
