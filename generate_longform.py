#!/usr/bin/env python3
"""
Generator CELEHO 8-10 min dokumentarneho scenara cez GitHub Models (zadarmo).
Pouzitie:
  python generate_longform.py "D.B. Cooper"        # konkretny pripad
  python generate_longform.py                        # vyberie nepouzity z banky
Vystup: scripts/<slug>.json  (potom: python make_video.py scripts/<slug>.json)
"""
import json, os, re, sys, requests

ROOT = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(ROOT, "longform_topics.json")
STATE = os.path.join(ROOT, "longform_used.json")

MODEL = os.environ.get("MODELS_MODEL", "openai/gpt-4o-mini")
BASE = os.environ.get("MODELS_BASE_URL", "https://models.github.ai/inference")
TOKEN = os.environ.get("MODELS_TOKEN") or os.environ.get("GITHUB_TOKEN")

SYSTEM = ("You are a scriptwriter for a respectful TRUE-CRIME / COLD-CASE YouTube DOCUMENTARY channel. "
          "You write a FULL 8 to 10 minute narration script about ONE famous, well-documented case in a "
          "serious documentary voice. SAFETY RULES: only real, widely-reported facts; NEVER invent names, "
          "dates or details; NEVER call anyone guilty unless they were actually convicted (for unsolved "
          "cases say it stays unsolved); be respectful to victims with NO graphic or gory detail; present "
          "theories AS theories. You output strict JSON, nothing else.")


def build_prompt(case):
    schema = {
        "title": "Punchy YouTube documentary title",
        "segments": [
            {"text": "One or two short spoken sentences.", "keywords": "foggy city night",
             "image": "OPTIONAL Wikimedia Commons search term for a real archival photo"}
        ],
        "description": "One line ending with 'Follow for more cold cases.'",
        "hashtags": ["#truecrime", "#coldcase", "#unsolved", "#documentary", "#shorts", "#fyp"],
    }
    return (
        f"Write a COMPLETE 8 to 10 minute faceless documentary narration script about this case: {case}.\n"
        "Return ONLY a JSON object with EXACTLY this schema (image is optional per segment):\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        "Rules:\n"
        "- 100 to 120 segments (this must fill 8 to 10 minutes of narration). Each segment = ONE or TWO short "
        "spoken sentences for a deep documentary voiceover.\n"
        "- Structure in order: a gripping cold-open HOOK (3-5 segments) -> background -> the event in detail "
        "-> the aftermath -> the investigation -> the theories/suspects (clearly AS theories) -> the legacy "
        "-> a final subscribe line.\n"
        "- Segment 1 hook: under 14 words, gripping, NEVER start with 'Did you know'.\n"
        "- 'keywords': 1-3 ENGLISH words for concrete cinematic STOCK footage that matches the line "
        "(e.g. 'foggy city night', 'old case files', 'vintage police car', 'dark forest', 'rain window night'). "
        "Cinematic and concrete, NEVER graphic or violent.\n"
        "- 'image': add ONLY for about 6 to 12 segments where a REAL archival photo almost certainly exists on "
        "Wikimedia Commons (a famous suspect sketch/poster, a famous building or landmark, a well-known "
        "historical photo, the specific type of aircraft/car/ship). Use a precise Commons search term. If you are "
        "not sure it exists, DO NOT add 'image' - most segments should have only 'keywords'.\n"
        "- ACCURACY IS SACRED: only real documented facts. Never invent.\n"
        "- the LAST segment 'text' MUST be exactly: 'Subscribe for cases the world never forgot.'\n"
        "- 'description': one sentence ending with 'Follow for more cold cases.'\n"
        "- 'hashtags': 6-8 tags including #truecrime #coldcase #documentary.\n"
        "Return ONLY the JSON object, no markdown."
    )


def call_model(user_text):
    r = requests.post(BASE.rstrip("/") + "/chat/completions",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"model": MODEL, "temperature": 0.8, "max_tokens": 8000,
              "messages": [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": user_text}]},
        timeout=300)
    if r.status_code >= 400:
        raise RuntimeError(f"Models API {r.status_code}: {r.text[:500]}")
    return r.json()["choices"][0]["message"]["content"]


def extract_json(s):
    s = s.strip()
    s = re.sub(r"^```(?:json)?", "", s).strip()
    s = re.sub(r"```$", "", s).strip()
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b != -1:
        s = s[a:b + 1]
    return json.loads(s)


def slug(t):
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")[:50] or "doc"


def pick_case():
    bank = json.load(open(BANK, encoding="utf-8")) if os.path.exists(BANK) else []
    used = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else []
    left = [c for c in bank if c not in used]
    return left[0] if left else (bank[0] if bank else None)


def main():
    if not TOKEN:
        print("CHYBA: chyba MODELS_TOKEN/GITHUB_TOKEN (lokalne daj PAT s 'models' scope do MODELS_TOKEN)")
        sys.exit(1)
    case = " ".join(sys.argv[1:]).strip() or pick_case()
    if not case:
        print("CHYBA: ziadny pripad (zadaj argument alebo napln longform_topics.json)"); sys.exit(1)
    print(f"Generujem 8-10 min scenar pre: {case}  (model {MODEL})...")
    spec = extract_json(call_model(build_prompt(case)))
    segs = spec.get("segments", [])
    # validacia + cistenie
    clean = []
    for s in segs:
        if isinstance(s, dict) and s.get("text") and s.get("keywords"):
            seg = {"text": str(s["text"]).strip(), "keywords": str(s["keywords"]).strip()}
            if s.get("image"):
                seg["image"] = str(s["image"]).strip()
            clean.append(seg)
    if len(clean) < 40:
        print(f"CHYBA: model vratil len {len(clean)} segmentov (cakal som 75-95)."); sys.exit(1)
    spec["segments"] = clean
    spec.setdefault("title", case)
    spec.setdefault("hashtags", ["#truecrime", "#coldcase", "#documentary", "#shorts", "#fyp"])
    os.makedirs(os.path.join(ROOT, "scripts"), exist_ok=True)
    path = os.path.join(ROOT, "scripts", slug(case) + ".json")
    json.dump(spec, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    imgs = sum(1 for s in clean if s.get("image"))
    print(f"OK: {len(clean)} segmentov ({imgs} s realnou fotkou) -> {path}")
    # zaznam do banky-stavu
    if case:
        used = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else []
        if case not in used:
            used.append(case)
            json.dump(used, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
