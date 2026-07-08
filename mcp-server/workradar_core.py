"""WorkRadar diagnosis engine — pure logic, no MCP dependency (unit-testable).

Turns a job (+ optional task/experience/AI-usage signals) into a directional,
honest AI-exposure diagnosis plus a "next move" route. Same data + honesty rules
as the WorkRadar web app: scores are hand-estimated directional references
(calibrated:false), never predictions.
"""
import json, os, re

_DIR = os.path.dirname(os.path.abspath(__file__))
JOBS = json.load(open(os.path.join(_DIR, "jobs.json"), encoding="utf-8"))
FULL_TEST = "https://idsexyhomme-code.github.io/1000/web/en/"

# AIOE anchors (Felten, Raj & Seamans 2021) — percentile only, mirrored from web.
AIOE = {
    "accountant": (99.0, "high"), "bookkeeper": (76.6, "high"), "call-center-agent": (73.2, "medium"),
    "copywriter": (74.1, "high"), "data-analyst": (95.2, "medium"), "graphic-designer": (67.0, "high"),
    "hr-manager": (89.5, "high"), "journalist": (82.0, "high"), "junior-developer": (82.6, "high"),
    "marketer": (97.4, "medium"), "nurse": (57.2, "high"), "office-admin": (78.2, "medium"),
    "paralegal": (87.3, "high"), "sales-rep": (69.4, "medium"), "teacher": (82.1, "medium"),
    "translator": (78.5, "high"), "video-editor": (73.8, "high"),
}

DISCLAIMER = ("Directional reference, not a prediction. AI-pressure scores are hand-estimated "
              "(uncalibrated) from public AI signals with a fixed, published method — not probabilities, "
              "and not a verdict on any person. High exposure means task reshuffling, not job deletion.")

# "Next move" routing (the connector: diagnosis -> the right kind of next action).
# resource is left generic/honest; concrete curated/affiliate resources slot in later.
NEXT_MOVE = {
    "defend": {"headline": "Stay and out-level the AI",
               "action": "Take your most-exposed task and put AI on the first pass — you own the judgment and the final call.",
               "resource_category": "AI-tool adoption for your exposed tasks + short task-specific upskilling"},
    "pivot": {"headline": "Shift toward the resilient core of your field",
              "action": "Move your week toward the hardest-to-automate parts of your role and let the routine parts compress.",
              "resource_category": "Adjacent-role reskilling within your field"},
    "reskill": {"headline": "Make a bigger jump to a less-exposed field",
                "action": "Your day-to-day is heavily exposed — invest in a structured move toward more resilient work.",
                "resource_category": "Structured reskilling / certification / bootcamp"},
    "independent": {"headline": "Sell your skills directly",
                    "action": "Package what you do into a service you own, instead of competing inside one employer.",
                    "resource_category": "Freelance platforms + personal-brand tools"},
    "founder": {"headline": "Build your own thing",
                "action": "Use AI as leverage to build a product or company around the judgment AI can't replace.",
                "resource_category": "No-code / build tools + founder communities"},
}


# Common ambiguous free-text titles -> the sensible canonical key (data has no
# generic "software engineer", so map the everyday phrasing people/AI will pass).
ALIASES = {
    "software engineer": "senior-developer", "software developer": "senior-developer",
    "developer": "senior-developer", "programmer": "senior-developer", "coder": "senior-developer",
    "swe": "senior-developer", "web developer": "web-developer", "front end developer": "frontend-developer",
    "backend developer": "backend-developer", "full stack developer": "senior-developer",
    "data scientist": "data-scientist", "product designer": "ux-designer", "designer": "graphic-designer",
    "physician": "doctor", "md": "doctor", "attorney": "lawyer", "cpa": "accountant",
    "customer service": "customer-service-representative", "customer support": "customer-service-representative",
    "sales": "sales-rep", "salesperson": "sales-rep", "marketing": "marketer", "hr": "hr-manager",
    "teacher": "teacher", "professor": "professor", "driver": "truck-driver", "writer": "content-writer",
}


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).strip()


def match_job(query):
    """Fuzzy-match a free-text job title to a jobs.json key. Returns key or None."""
    q = _norm(query)
    q = re.sub(r"^(i am|i m|im|i work as|my job is|my role is|i work in)\s+", "", q)  # strip filler
    q = re.sub(r"^(an?|the)\s+", "", q).strip()
    if not q:
        return None
    if q in ALIASES and ALIASES[q] in JOBS:          # common-phrasing aliases
        return ALIASES[q]
    slug = q.replace(" ", "-")
    if slug in JOBS:
        return slug
    names = {k: _norm(v["name"]) for k, v in JOBS.items()}
    for k, n in names.items():                       # exact name
        if n == q:
            return k
    cand = [(k, n) for k, n in names.items() if q in n or n in q]  # substring
    if cand:
        return min(cand, key=lambda kn: abs(len(kn[1]) - len(q)))[0]
    qt = set(q.split())                              # token overlap → prefer most overlap, fewest extra words
    ranked = []
    for k, n in names.items():
        nt = set(n.split())
        ov = len(qt & nt)
        if ov:
            ranked.append((ov, -(len(nt - qt)), -len(n), k))   # overlap↑, extra-words↓, shorter name↑
    if not ranked:
        return None
    ranked.sort(reverse=True)
    return ranked[0][3]


def band(score):
    if score < 25:  return ("Clear", "low")
    if score < 45:  return ("Partly cloudy", "moderate")
    if score < 65:  return ("Cloudy", "elevated")
    return ("Storm", "high")


def _suggest_branch(score):
    # Directional default when we lack the person's feelings/instinct signals.
    if score >= 65:  return "reskill"
    if score >= 45:  return "pivot"
    return "defend"


def assess(job, tasks=None, experience_years=None, uses_ai_tools=None):
    """Diagnose AI exposure for a job. See module docstring for honesty rules."""
    key = match_job(job)
    if not key:
        sugg = search(job, 5)
        msg = ("No confident match. Try one of these or rephrase."
               if sugg else "No match found — rephrase with a common job title (e.g. 'nurse', 'accountant').")
        return {"matched": False, "query": job, "message": msg,
                "suggestions": sugg, "full_report_url": FULL_TEST}
    j = JOBS[key]
    hi = j.get("hi", []); lo = j.get("lo", [])
    base = j["base"]

    # task-weighted personalization (mirrors web "your tasks" idea)
    picked = []
    if tasks:
        alltask = hi + lo
        for t in tasks:
            tn = _norm(t)
            hit = next((pair for pair in alltask if tn in _norm(pair[0]) or _norm(pair[0]) in tn), None)
            if hit:
                picked.append(hit)
    score = round(sum(v for _, v in picked) / len(picked)) if picked else base

    # AI-usage delta (using AI lowers your personal exposure narrative; matches web)
    u = _norm(uses_ai_tools or "")
    if u:
        if "daily" in u or "every" in u or "lot" in u:   score -= 4
        elif "some" in u or "occasion" in u:             score -= 2
        elif "never" in u or "rare" in u or "barely" in u: score += 2
    score = max(0, min(100, score))

    bname, blevel = band(score)
    branch = _suggest_branch(score)
    nm = NEXT_MOVE[branch]

    out = {
        "matched": True,
        "job": j["name"],
        "job_key": key,
        "ai_pressure": score,
        "band": bname,
        "exposure_level": blevel,
        "most_exposed_tasks": [{"task": t, "pressure": v} for t, v in hi[:3]],
        "most_resilient_tasks": [{"task": t, "pressure": v} for t, v in lo[:2]],
        "interpretation": (
            f"{j['name']} work carries an estimated AI-pressure of {score}/100 ({bname.lower()}). "
            f"The most exposed parts are {', '.join(t.lower() for t, _ in hi[:3]) or 'routine tasks'}; "
            f"the most resilient are {', '.join(t.lower() for t, _ in lo[:2]) or 'judgment-heavy work'}."),
        "suggested_path": branch,
        "next_move": {"path": branch, **nm},
        "full_report_url": f"{FULL_TEST}?job={key}",
        "disclaimer": DISCLAIMER,
    }
    if key in AIOE:
        p, c = AIOE[key]
        out["external_anchor"] = {
            "source": "AIOE (Felten, Raj & Seamans 2021)",
            "percentile": p, "confidence": c,
            "note": f"Cross-referenced: this occupation ranks top {round(100 - p)}% for AI exposure"
                    + (" (proxy SOC match)" if c != "high" else "") + ".",
        }
    if picked:
        out["scored_from"] = "your selected tasks"
    return out


def compare(job_a, job_b):
    a, b = match_job(job_a), match_job(job_b)
    if not a or not b:
        return {"matched": False, "message": "Could not match both jobs.",
                "job_a": a and JOBS[a]["name"], "job_b": b and JOBS[b]["name"]}
    sa, sb = JOBS[a]["base"], JOBS[b]["base"]
    more = JOBS[a]["name"] if sa >= sb else JOBS[b]["name"]
    return {"matched": True,
            "job_a": {"job": JOBS[a]["name"], "ai_pressure": sa},
            "job_b": {"job": JOBS[b]["name"], "ai_pressure": sb},
            "more_exposed": more, "difference": abs(sa - sb),
            "disclaimer": DISCLAIMER}


def search(query, limit=8):
    q = _norm(query)
    hits = [(k, v["name"], v["base"]) for k, v in JOBS.items() if q in _norm(v["name"])]
    if not q:
        hits = [(k, v["name"], v["base"]) for k, v in JOBS.items()]
    hits.sort(key=lambda x: len(x[1]))
    return [{"job": n, "job_key": k, "ai_pressure": b} for k, n, b in hits[:limit]]
