#!/usr/bin/env python3
"""Doplni banku tem cez GitHub Models (zadarmo). Nika: TRUE CRIME / cold cases (bezpecne, faktualne)."""
import json
import os
import re
import sys

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(ROOT, "topics_bank.json")
STATE = os.path.join(ROOT, "used_topics.json")

TARGET = int(os.environ.get("TOPICS_TARGET", "15"))
MODEL = os.environ.get("MODELS_MODEL", "openai/gpt-4o-mini")
BASE = os.environ.get("MODELS_BASE_URL", "https://models.github.ai/inference")
TOKEN = os.environ.get("MODELS_TOKEN") or os.environ.get("GITHUB_TOKEN")

SYSTEM = ("You are a scriptwriter for a respectful TRUE-CRIME / cold-case brand. You retell FAMOUS, "
          "widely-documented cases (heists, disappearances, unsolved mysteries, historic cases) in a "
          "serious documentary voice. STRICT SAFETY RULES: (1) ACCURACY IS SACRED - only real, "
          "widely-reported facts; never invent details, names, dates or motives. (2) NEVER accuse or name "
          "any person as guilty unless they were actually convicted; for unsolved cases say it remains "
          "unsolved. (3) Be RESPECTFUL to victims - no graphic, gory or gratuitous detail, no "
          "sensationalizing suffering. (4) Prefer older, famous, well-documented cases; avoid recent cases "
          "involving private individuals. (5) Present theories AS theories, never as fact. "
          "You output strict JSON, nothing else.")

EXAMPLE = {
    "title": "The Man Who Vanished With $200,000",
    "segments": [
        {"text": "In 1971, a man calling himself D.B. Cooper hijacked a passenger plane.", "keywords": "vintage airplane sky"},
        {"text": "He demanded two hundred thousand dollars and four parachutes.", "keywords": "cash money stack"},
        {"text": "After releasing the passengers, he got his money.", "keywords": "airport night runway"},
        {"text": "Then, somewhere over the forests, he jumped from the plane.", "keywords": "dark forest aerial"},
        {"text": "He was never found, and the case remains unsolved to this day.", "keywords": "foggy forest trees"},
        {"text": "A man who vanished into the night, and into legend.", "keywords": "cloudy mountain sky"},
        {"text": "Follow for cases the world never forgot.", "keywords": "old case files"},
    ],
    "description": "In 1971 D.B. Cooper hijacked a plane, jumped out with the ransom, and was never found. Follow for daily cold cases!",
    "hashtags": ["#truecrime", "#dbcooper", "#unsolved", "#coldcase", "#mystery", "#shorts", "#fyp", "#casefiles"],
}


def build_prompt(n, existing_titles):
    return (
        f"Generate {n} NEW faceless short-form video topics for a respectful TRUE-CRIME / COLD-CASE brand "
        "(TikTok / Reels / YouTube Shorts).\n"
        "Focus: FAMOUS, widely-documented cases - daring heists, mysterious disappearances, unsolved "
        "historic cases, real cases that gripped the world. Mostly older / well-known.\n"
        "Return ONLY a JSON array (no markdown). Each item EXACTLY this schema:\n"
        f"{json.dumps(EXAMPLE, ensure_ascii=False, indent=2)}\n\n"
        "SAFETY RULES (critical):\n"
        "- ACCURACY IS SACRED: only real, widely-reported facts. NEVER invent names, dates, details or motives.\n"
        "- NEVER call anyone guilty unless they were actually convicted. For unsolved cases, say it stays unsolved.\n"
        "- RESPECT victims: no graphic, gory or gratuitous detail; never sensationalize suffering.\n"
        "- Prefer famous older cases; avoid recent crimes involving private individuals.\n"
        "- Present theories AS theories, never as fact.\n\n"
        "Style rules (make it PRO and gripping):\n"
        "- title: punchy and curiosity-driven, e.g. 'The Heist That Was Never Solved', 'The Plane That Vanished'.\n"
        "- 6 to 9 segments. Segment 1 is THE HOOK: a gripping true line under 14 words. Never start with 'Did you know'.\n"
        "- build the story line by line; write for a deep, serious documentary SPOKEN voiceover: short clear sentences.\n"
        "- each segment 'keywords': 1-3 ENGLISH words for real Pexels footage that VISUALLY MATCHES the line "
        "(e.g. 'foggy city night', 'old case files', 'empty road night', 'vintage police car', 'dark forest'). "
        "Cinematic and concrete, NEVER graphic or violent.\n"
        "- the SECOND-TO-LAST segment loops back to the opening hook so a rewatch feels seamless.\n"
        "- the LAST segment text MUST be exactly: 'Follow for cases the world never forgot.'\n"
        "- description: one sentence ending with 'Follow for daily cold cases!'.\n"
        "- hashtags: 6-8 tags including #truecrime #coldcase #shorts #fyp.\n"
        f"- Do NOT reuse any of these existing titles: {existing_titles}\n"
        "Return ONLY the JSON array."
    )


def call_model(user_text):
    r = requests.post(
        BASE.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"model": MODEL, "temperature": 0.85,
              "messages": [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": user_text}]},
        timeout=180,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"Models API {r.status_code}: {r.text[:500]}")
    return r.json()["choices"][0]["message"]["content"]


def extract_json(s):
    s = s.strip()
    s = re.sub(r"^```(?:json)?", "", s).strip()
    s = re.sub(r"```$", "", s).strip()
    a, b = s.find("["), s.rfind("]")
    if a != -1 and b != -1:
        s = s[a:b + 1]
    return json.loads(s)


def valid(t):
    if not isinstance(t, dict) or "title" not in t or "segments" not in t:
        return False
    if not isinstance(t["segments"], list) or len(t["segments"]) < 4:
        return False
    for seg in t["segments"]:
        if "text" not in seg or "keywords" not in seg:
            return False
    t.setdefault("description", t["title"] + " Follow for daily cold cases!")
    t.setdefault("hashtags", ["#truecrime", "#coldcase", "#shorts", "#fyp"])
    return True


def main():
    if not TOKEN:
        print("CHYBA: chyba MODELS_TOKEN/GITHUB_TOKEN"); sys.exit(1)
    bank = json.load(open(BANK, encoding="utf-8"))
    used = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else []
    titles = {t["title"] for t in bank}
    unused = [t for t in bank if t["title"] not in used]
    need = TARGET - len(unused)
    if need <= 0:
        print(f"Banka OK: {len(unused)} nepouzitych tem."); return
    print(f"Generujem ~{need} novych tem cez {MODEL}...")
    items = extract_json(call_model(build_prompt(need + 3, sorted(titles))))
    added = 0
    for t in items:
        if not valid(t) or t["title"] in titles:
            continue
        bank.append(t); titles.add(t["title"]); added += 1
    json.dump(bank, open(BANK, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"Pridanych {added} tem. Banka ma {len(bank)} tem.")


if __name__ == "__main__":
    main()
