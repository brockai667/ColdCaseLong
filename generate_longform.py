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


DEFAULT_CHAPTERS = [
    "Cold open: a gripping hook", "Who they were / the background",
    "The day it happened", "The investigation", "The key evidence",
    "The prime suspects and theories", "What happened next", "The legacy today",
]


def outline_prompt(case):
    return (
        f"Plan a 13 to 15 minute faceless true-crime DOCUMENTARY about this case: {case}.\n"
        "Return ONLY JSON with this schema:\n"
        '{\n  "title": "Punchy YouTube documentary title (max 70 chars)",\n'
        '  "description": "One sentence ending with \'Follow for more cold cases.\'",\n'
        '  "hashtags": ["#truecrime","#coldcase","#unsolved","#documentary","#mystery","#fyp"],\n'
        '  "chapters": ["Cold open hook","Background","The event","..."]\n}\n'
        "Give 8 chapter titles that, in order, tell the WHOLE story: a gripping cold-open hook, "
        "the background, the event in detail, the aftermath, the investigation, the key evidence, the "
        "suspects, the theories (clearly AS theories), later developments, and the legacy. "
        "Real, widely-documented facts only. Return ONLY the JSON, no markdown."
    )


def chapter_prompt(case, title, chapter, idx, total, prev_tail):
    return (
        f"Faceless true-crime documentary titled \"{title}\" about: {case}.\n"
        f"Write ONLY chapter {idx} of {total}: \"{chapter}\".\n"
        + (f"The previous chapter ended with: {prev_tail}\n" if prev_tail else "")
        + "Write 9 to 11 segments for THIS chapter only. Each segment = ONE or TWO short spoken "
        "documentary sentences for a deep voiceover. Move the story FORWARD; do NOT repeat earlier lines; "
        "do NOT write any closing or 'subscribe' line.\n"
        + ("Chapter 1 first segment is the HOOK: under 14 words, gripping, NEVER start with 'Did you know'.\n"
           if idx == 1 else "")
        + "SAFETY: only real documented facts; never invent names/dates; theories AS theories; "
        "respectful, no graphic detail.\n"
        "'keywords' = 1-3 ENGLISH words for concrete cinematic STOCK footage matching the line "
        "(e.g. 'foggy city night','old case files','vintage police car','dark forest','rain window night'). "
        "Add 'image' to ONLY 1-2 segments here, and ONLY if a REAL archival photo almost certainly exists on "
        "Wikimedia Commons (a famous suspect sketch/poster, a famous building/landmark, a well-known historical "
        "photo, the specific aircraft/car/ship type) - use a precise Commons search term; otherwise omit 'image'.\n"
        "Return ONLY JSON: {\"segments\": [ {\"text\": \"...\", \"keywords\": \"...\", \"image\": \"OPTIONAL\"} ] }."
    )


def continue_prompt(title, segs, n):
    recent = " | ".join(s["text"] for s in segs[-6:])
    return (
        f"Continue this true-crime documentary titled \"{title}\".\n"
        f"Recent lines so far: {recent}\n"
        f"Add EXACTLY {n} MORE segments that move the story FORWARD (deeper into the investigation, "
        "evidence, suspects and theories presented clearly AS theories, public reaction, and legacy). "
        "Do NOT repeat anything already said. Do NOT include any closing or subscribe line.\n"
        "Same rules: each segment = one or two short documentary sentences; 'keywords' = 1-3 ENGLISH words "
        "for concrete cinematic stock footage; optional 'image' = a precise Wikimedia Commons search term "
        "ONLY if a real archival photo almost certainly exists. ACCURACY IS SACRED, only real facts.\n"
        "Return ONLY a JSON object: {\"segments\": [ {\"text\": \"...\", \"keywords\": \"...\"} ] }."
    )


import time as _time

# hlavny model + zalozne (ak hlavny je pod limitom / padne, skusi sa dalsi zadarmo)
_MODELS = [MODEL] + [m.strip() for m in os.environ.get(
    "MODELS_FALLBACK", "openai/gpt-4.1-mini,openai/gpt-4o").split(",")
    if m.strip() and m.strip() != MODEL]
_MIN_GAP = float(os.environ.get("MODELS_MIN_GAP", "4"))   # rozostup (s) medzi volaniami -> limit za minutu
_last = [0.0]


def call_model(user_text):
    gap = _MIN_GAP - (_time.time() - _last[0])            # nenaraz na limit poctu volani za minutu
    if gap > 0:
        _time.sleep(gap)
    last = "?"
    for model in _MODELS:                                 # hlavny model, potom zalozne
        for attempt in range(4):                          # opakuj pri 429 / 5xx (rate limit / pretazenie)
            try:
                r = requests.post(BASE.rstrip("/") + "/chat/completions",
                    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
                    json={"model": model, "temperature": 0.8, "max_tokens": 12000,
                          "response_format": {"type": "json_object"},
                          "messages": [{"role": "system", "content": SYSTEM},
                                       {"role": "user", "content": user_text}]},
                    timeout=300)
            except Exception as e:
                last = "exc %s" % str(e)[:120]; _time.sleep(6); continue
            if r.status_code == 429 or r.status_code >= 500:      # limit / pretazenie -> pockaj a skus znova
                last = "%s %s" % (r.status_code, r.text[:150])
                wait = 8 * (attempt + 1)
                ra = r.headers.get("Retry-After")                # respektuj Retry-After ak ho server posle
                if ra:
                    try: wait = max(wait, min(90, int(float(ra))))
                    except Exception: pass
                print("[%s pokus %d/4] %s -> cakam %ds" % (model, attempt + 1, r.status_code, wait))
                _time.sleep(wait); continue
            if r.status_code >= 400:                              # ina chyba -> skus dalsi model
                last = "%s %s" % (r.status_code, r.text[:200]); break
            _last[0] = _time.time()
            return r.json()["choices"][0]["message"]["content"]
    _last[0] = _time.time()
    raise RuntimeError("Models API zlyhalo (vsetky modely): %s" % last)


def extract_json(s):
    s = s.strip()
    s = re.sub(r"^```(?:json)?", "", s).strip()
    s = re.sub(r"```$", "", s).strip()
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b != -1:
        s = s[a:b + 1]
    s = re.sub(r",(\s*[}\]])", r"\1", s)   # odstran trailing commas (casta chyba modelu)
    return json.loads(s)


def slug(t):
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")[:50] or "doc"


def refill_bank(min_unused=4, target=8):
    """Ak v banke ostava malo nepouzitych pripadov, AI dogeneruje dalsie REALNE slavne
    cold-case / nevyriesene pripady (dedup). Vdaka tomu napady nikdy nedojdu."""
    bank = json.load(open(BANK, encoding="utf-8")) if os.path.exists(BANK) else []
    used = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else []
    unused = [c for c in bank if c not in used]
    if len(unused) >= min_unused or not TOKEN:
        return bank
    have_lc = {c.strip().lower() for c in bank}
    avoid = "; ".join(bank[-25:])
    prompt = (
        f"List {target} FAMOUS, REAL, widely-documented true-crime cases suitable for a respectful "
        "YouTube documentary: unsolved mysteries, cold cases, famous heists/robberies, notorious "
        "disappearances or historical crimes. Each must be a REAL, well-reported case (no fiction, no "
        "made-up names). Do NOT include any of these already-used ones: " + avoid + ".\n"
        'Return ONLY JSON: {"cases": ["The Zodiac Killer case", "The disappearance of ...", "..."]}. '
        "Use a clear, specific case name for each."
    )
    try:
        data = extract_json(call_model(prompt))
        new = data.get("cases", []) if isinstance(data, dict) else []
    except Exception as e:
        print(f"[refill zlyhal: {e}]"); return bank
    added = 0
    for c in new:
        c = str(c).strip()
        if 6 <= len(c) <= 90 and c.lower() not in have_lc:
            bank.append(c); have_lc.add(c.lower()); added += 1
    if added:
        json.dump(bank, open(BANK, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"[refill] pridanych {added} novych pripadov do banky (spolu {len(bank)})")
    return bank


def pick_case():
    bank = refill_bank()
    used = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else []
    used_lc = {u.strip().lower() for u in used}
    left = [c for c in bank if c.strip().lower() not in used_lc]
    return left[0] if left else (bank[0] if bank else None)


def main():
    if not TOKEN:
        print("CHYBA: chyba MODELS_TOKEN/GITHUB_TOKEN (lokalne daj PAT s 'models' scope do MODELS_TOKEN)")
        sys.exit(1)
    case = " ".join(sys.argv[1:]).strip() or pick_case()
    if not case:
        print("CHYBA: ziadny pripad (zadaj argument alebo napln longform_topics.json)"); sys.exit(1)
    print(f"Generujem 8-10 min scenar pre: {case}  (model {MODEL}, po kapitolach)...")

    def add_segments(raw, clean, have):
        added = 0
        for s in raw:
            if not (isinstance(s, dict) and s.get("text") and s.get("keywords")):
                continue
            txt = str(s["text"]).strip()
            if not txt or txt.lower() in have:
                continue
            seg = {"text": txt, "keywords": str(s["keywords"]).strip()}
            if s.get("image"):
                seg["image"] = str(s["image"]).strip()
            clean.append(seg); have.add(txt.lower()); added += 1
        return added

    # 1) osnova (titulok, popis, hashtagy, kapitoly)
    try:
        plan = extract_json(call_model(outline_prompt(case)))
    except Exception as e:
        print(f"[osnova zlyhala: {e}] pouzivam default kapitoly")
        plan = {}
    spec = {
        "title": (plan.get("title") or case).strip(),
        "description": (plan.get("description") or f"The full story of {case}. Follow for more cold cases.").strip(),
        "hashtags": plan.get("hashtags") or ["#truecrime", "#coldcase", "#unsolved", "#documentary", "#mystery", "#fyp"],
    }
    chapters = [c for c in (plan.get("chapters") or []) if isinstance(c, str) and c.strip()] or DEFAULT_CHAPTERS
    chapters = chapters[:12]
    print(f"Titulok: {spec['title']}  |  {len(chapters)} kapitol")

    # 2) generuj kazdu kapitolu zvlast (spolahlivo nazbiera ~100-140 segmentov)
    clean, have = [], set()
    for i, ch in enumerate(chapters, 1):
        tail = " ".join(s["text"] for s in clean[-3:])
        try:
            part = extract_json(call_model(chapter_prompt(case, spec["title"], ch, i, len(chapters), tail)))
        except Exception as e:
            print(f"[kapitola {i} '{ch[:30]}' zlyhala: {e}]"); continue
        a = add_segments(part.get("segments", []), clean, have)
        print(f"[kapitola {i}/{len(chapters)}] +{a}  spolu {len(clean)}")

    # 3) poistka na dlzku: ak je malo, doziadaj este (continuation)
    tries = 0
    while len(clean) < 72 and tries < 3:
        tries += 1
        try:
            more = extract_json(call_model(continue_prompt(spec["title"], clean, min(30, 85 - len(clean)))))
        except Exception as e:
            print(f"[continuation {tries}] {e}"); break
        a = add_segments(more.get("segments", []), clean, have)
        print(f"[continuation {tries}] +{a}  spolu {len(clean)}")
        if a == 0:
            break

    # 4) zaveracia (subscribe) veta
    closing = "Subscribe for cases the world never forgot."
    if not clean or clean[-1]["text"] != closing:
        clean.append({"text": closing, "keywords": "dark cinematic city night"})

    if len(clean) < 40:
        print(f"CHYBA: po vsetkych pokusoch len {len(clean)} segmentov."); sys.exit(1)
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
