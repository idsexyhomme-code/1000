#!/usr/bin/env python3
"""직업 대량 생성기 — Gemini로 직무 엔트리를 생성→엄격검증→중복제거→jobs.json 병합.
점수는 directional 손추정(calibrated:false 원칙 유지). 키는 env GEMINI_API_KEY.
사용: GEMINI_API_KEY=... python3 tools/gen_jobs.py <target_total> [categories_csv]
"""
import json
import os
import re
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "web", "en", "jobs.json")
KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-2.5-flash"
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}"

CATEGORIES = [
    "skilled trades (construction, repair, mechanical)",
    "healthcare specialists and allied health",
    "personal care and grooming (incl. pet groomer, barber, esthetician)",
    "hospitality, food service, and culinary",
    "agriculture, fishing, forestry, and animal care",
    "logistics, transport, warehouse, and delivery",
    "manufacturing, production, and assembly",
    "creative, arts, design, and performance",
    "media, writing, and publishing",
    "finance, accounting, and insurance",
    "legal and compliance",
    "science, research, and laboratory",
    "education and training",
    "engineering and architecture",
    "information technology and software",
    "sales, marketing, and advertising",
    "administration, HR, and operations",
    "public service, safety, and government",
    "real estate, property, and facilities",
    "beauty, fashion, and wellness",
    "sports, fitness, and recreation",
    "maritime, aviation, and rail",
    "energy, utilities, and environment",
    "retail, customer service, and commerce",
    "niche and emerging professions (specialty crafts, unusual trades)",
]

PROMPT = """Generate {n} DISTINCT real-world job titles in the category: {cat}.
Include specialized/niche ones, not just the obvious. Avoid generic duplicates.

For EACH job output an object with EXACTLY these keys:
- "id": kebab-case unique slug (e.g. "pet-groomer")
- "name": human title (e.g. "Pet Groomer")
- "emoji": one fitting emoji
- "base": integer 8-96 = overall exposure to AI/automation.
   Manual/physical/hands-on/care jobs LOW (~15-35).
   Content/data/admin/routine-cognitive jobs HIGH (~62-88).
   Mixed jobs MID (~40-60). Be honest and varied, not all high.
- "hi": array of EXACTLY 3 [task, score] for the MOST AI-exposed tasks (scores ~58-90)
- "lo": array of EXACTLY 2 [task, score] for the LEAST AI-exposed tasks (scores ~12-42)
Tasks must be real, specific to the job, short (2-4 words).

Return ONLY a JSON object keyed by id, no markdown, no commentary. Example one entry:
{{"pet-groomer":{{"name":"Pet Groomer","emoji":"✂️","base":22,"hi":[["Appointment scheduling",60],["Client reminders",58],["Breed style lookup",55]],"lo":[["Hands-on grooming",16],["Animal handling",14]]}}}}
"""


def call(cat, n=22):
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(n=n, cat=cat)}]}],
        "generationConfig": {"temperature": 0.95, "maxOutputTokens": 20000},
    }
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.load(r)
    txt = d["candidates"][0]["content"]["parts"][0]["text"]
    txt = re.sub(r"^```(json)?|```$", "", txt.strip(), flags=re.M).strip()
    return json.loads(txt)


def valid(job):
    try:
        if not (isinstance(job.get("name"), str) and job["name"].strip()):
            return False
        if not (isinstance(job.get("emoji"), str) and job["emoji"].strip()):
            return False
        b = job.get("base")
        if not (isinstance(b, int) and 8 <= b <= 96):
            return False
        for k, cnt in (("hi", 3), ("lo", 2)):
            arr = job.get(k)
            if not (isinstance(arr, list) and len(arr) == cnt):
                return False
            for it in arr:
                if not (isinstance(it, list) and len(it) == 2):
                    return False
                if not (isinstance(it[0], str) and it[0].strip()):
                    return False
                if not (isinstance(it[1], int) and 0 <= it[1] <= 100):
                    return False
        return True
    except Exception:
        return False


def main():
    if not KEY:
        print("GEMINI_API_KEY 없음")
        sys.exit(1)
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    cats = sys.argv[2].split(",") if len(sys.argv) > 2 else CATEGORIES

    jobs = json.load(open(JOBS, encoding="utf-8"))
    names = {jobs[k]["name"].lower() for k in jobs}
    start = len(jobs)
    print(f"시작: {start}개, 목표 {target}")

    rounds = 0
    ci = 0
    while len(jobs) < target and rounds < 80:
        cat = cats[ci % len(cats)]
        ci += 1
        rounds += 1
        try:
            batch = call(cat)
        except Exception as e:
            print(f"  [{rounds}] {cat[:30]}.. 호출실패: {str(e)[:60]}")
            time.sleep(2)
            continue
        added = 0
        for jid, job in batch.items():
            jid = re.sub(r"[^a-z0-9-]", "", str(jid).lower())[:40]
            if not jid or jid in jobs:
                continue
            if not valid(job):
                continue
            nm = job["name"].lower()
            if nm in names:
                continue
            jobs[jid] = {
                "name": job["name"],
                "emoji": job["emoji"],
                "base": job["base"],
                "hi": [[t[0], t[1]] for t in job["hi"]],
                "lo": [[t[0], t[1]] for t in job["lo"]],
            }
            names.add(nm)
            added += 1
            if len(jobs) >= target:
                break
        print(f"  [{rounds}] {cat[:34]:34} +{added} (총 {len(jobs)})")
        if rounds % 5 == 0:  # 중간 저장(긴 실행 안전)
            json.dump(jobs, open(JOBS, "w", encoding="utf-8"), ensure_ascii=False)

    json.dump(jobs, open(JOBS, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"완료: {start} -> {len(jobs)} (+{len(jobs)-start})")


if __name__ == "__main__":
    main()
