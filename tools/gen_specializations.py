#!/usr/bin/env python3
"""인기 직업 '세부 전문화' 생성기 — 부모 직업의 실제 하위 역할을 생성.
핵심: 같은 직군 안에서도 AI 노출이 다르게(차등) 나오도록 강제. 점수=directional 손추정.
사용: GEMINI_API_KEY=... python3 tools/gen_specializations.py [parents_csv]
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

PARENTS = [
    "Software Developer", "Data Scientist", "Registered Nurse", "Physician",
    "Teacher", "Accountant", "Marketing Manager", "Graphic Designer", "Lawyer",
    "Mechanical Engineer", "Civil Engineer", "Sales Representative", "Writer",
    "Financial Analyst", "Project Manager", "Consultant", "Customer Support Rep",
    "Human Resources Manager", "Product Manager", "UX Designer", "Photographer",
    "Chef", "Real Estate Agent", "Therapist", "Pharmacist", "Architect",
    "Electrician", "Social Media Manager", "Recruiter", "Operations Manager",
    "Video Editor", "Translator", "Research Scientist", "Business Analyst",
]

PROMPT = """List {n} distinct, REAL specializations (sub-roles) of the occupation: "{parent}".
Each must be a recognized sub-role people actually hold.
Example for "Registered Nurse": ICU Nurse, ER Nurse, Dialysis Nurse, Oncology Nurse,
Nurse Informaticist, Telehealth Nurse, School Nurse, Labor & Delivery Nurse.

CRITICAL — VARY the AI exposure across these specializations honestly:
- Admin/data/remote/documentation-heavy sub-roles = HIGHER base (~60-85).
- Hands-on/high-stakes/relationship-heavy sub-roles = LOWER base (~15-40).
- The base scores within this list MUST genuinely differ (do not make them all similar).

For EACH output an object with EXACTLY:
- "id": kebab-case unique slug including the specialization (e.g. "icu-nurse")
- "name": full title (e.g. "ICU Nurse")
- "emoji": one fitting emoji
- "base": integer 8-96 (overall AI/automation exposure, per the rule above)
- "hi": EXACTLY 3 [task, score] most AI-exposed tasks (scores ~58-90)
- "lo": EXACTLY 2 [task, score] least AI-exposed tasks (scores ~12-42)
Tasks: real, specific to THIS specialization, 2-4 words.

Return ONLY a JSON object keyed by id. No markdown, no commentary."""


def call(parent, n=12):
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(n=n, parent=parent)}]}],
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 16000},
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
        if not (isinstance(job.get("base"), int) and 8 <= job["base"] <= 96):
            return False
        for k, c in (("hi", 3), ("lo", 2)):
            a = job.get(k)
            if not (isinstance(a, list) and len(a) == c):
                return False
            for it in a:
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
    parents = sys.argv[1].split(",") if len(sys.argv) > 1 else PARENTS
    jobs = json.load(open(JOBS, encoding="utf-8"))
    names = {jobs[k]["name"].lower() for k in jobs}
    start = len(jobs)
    print(f"시작 {start}개, 부모 {len(parents)}개")
    for i, parent in enumerate(parents, 1):
        try:
            batch = call(parent)
        except Exception as e:
            print(f"  [{i}] {parent:24} 실패: {str(e)[:50]}")
            time.sleep(2)
            continue
        added, bases = 0, []
        for jid, job in batch.items():
            jid = re.sub(r"[^a-z0-9-]", "", str(jid).lower())[:48]
            if not jid or jid in jobs or not valid(job):
                continue
            nm = job["name"].lower()
            if nm in names:
                continue
            jobs[jid] = {
                "name": job["name"], "emoji": job["emoji"], "base": job["base"],
                "hi": [[t[0], t[1]] for t in job["hi"]],
                "lo": [[t[0], t[1]] for t in job["lo"]],
            }
            names.add(nm)
            bases.append(job["base"])
            added += 1
        spread = f"{min(bases)}-{max(bases)}" if bases else "-"
        print(f"  [{i}] {parent:24} +{added}  (노출 {spread})  총 {len(jobs)}")
        if i % 5 == 0:
            json.dump(jobs, open(JOBS, "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(jobs, open(JOBS, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"완료 {start} -> {len(jobs)} (+{len(jobs)-start})")


if __name__ == "__main__":
    main()
